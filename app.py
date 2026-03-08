import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
import plotly.graph_objects as go
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import pytz

# 1. 페이지 설정 및 제목
st.set_page_config(page_title="SOXL 스마트 퀀트 비서 v2.9", layout="wide")

# 2. 미국 시장 날짜 계산 (미국 시간 기준 다음 영업일 자동 계산)
def get_trading_date():
    tz_et = pytz.timezone('US/Eastern')
    now_et = datetime.now(tz_et)
    target = now_et
    # 장 마감(16시) 이후거나 주말이면 다음 영업일로
    if now_et.hour >= 16 or now_et.weekday() >= 5:
        days_to_add = 1
        if now_et.weekday() == 4: days_to_add = 3 # 금 -> 월
        elif now_et.weekday() == 5: days_to_add = 2 # 토 -> 월
        target += timedelta(days=days_to_add)
    return target.strftime('%Y-%m-%d')

trade_date = get_trading_date()

# 3. 데이터 로드 함수 (캐싱 적용)
@st.cache_data(ttl=3600)
def get_volatility():
    ticker = yf.Ticker("SOXL")
    hist = ticker.history(period="10d")
    return round((hist['High'] - hist['Low']).tail(5).mean(), 2)

@st.cache_data(ttl=60)
def get_market_summary():
    ticker = yf.Ticker("SOXL")
    hist = ticker.history(period="1d")
    if hist.empty: return 0.0, 0.0
    curr = round(hist['Close'].iloc[-1], 2)
    vwap = round((hist['High'].iloc[-1] + hist['Low'].iloc[-1] + hist['Close'].iloc[-1]) / 3, 2)
    return curr, vwap

# 4. 전문가용 캔들스틱 차트 (이동평균선 포함 & 휴장기 제거)
def show_candle_chart():
    st.subheader("📊 SOXL 실시간 분석 차트")
    t_frame = st.radio("기간 선택", ["시간단위", "일단위", "주단위", "월단위"], horizontal=True)
    
    params = {
        "시간단위": {"period": "2d", "interval": "15m"}, 
        "일단위": {"period": "7d", "interval": "30m"}, 
        "주단위": {"period": "1mo", "interval": "1d"}, 
        "월단위": {"period": "1y", "interval": "1wk"}
    }
    
    ticker = yf.Ticker("SOXL")
    df = ticker.history(**params[t_frame])
    if df.empty: return

    # 이동평균선 계산
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    
    fig = go.Figure()

    # 캔들스틱 추가
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        name='가격', increasing_line_color='#FF3232', decreasing_line_color='#0066FF'
    ))

    # 이동평균선 추가
    fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#FF3232', width=1.5), name='5일선'))
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#FFD700', width=1.5), name='20일선'))

    # 휴장 시간 제거 설정
    fig.update_xaxes(
        rangebreaks=[
            dict(bounds=["sat", "mon"]), # 주말 제거
            dict(bounds=[16, 9.5], pattern="hour") # 밤 시간 제거
        ]
    )
    
    fig.update_layout(
        height=500, margin=dict(l=10, r=10, t=10, b=10),
        xaxis_rangeslider_visible=False, template="plotly_white", hovermode='x unified'
    )
    st.plotly_chart(fig, use_container_width=True)

# 5. 구글 시트 연결
try:
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    info = dict(st.secrets["gcp_service_account"])
    info["private_key"] = info["private_key"].replace("\\n", "\n").strip()
    creds = Credentials.from_service_account_info(info, scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open("soxl invest").sheet1
    all_records = sheet.get_all_records()
except Exception as e:
    st.error("구글 시트 연결에 실패했습니다.Secrets 설정을 확인해주세요.")
    st.stop()

# 현재 계좌 정보 계산
if all_records:
    last = all_records[-1]
    cash = float(str(last.get('잔고', 10000)).replace(',', ''))
    stocks = int(last.get('주식수', 0))
    cycle = int(last.get('사이클회차', 1))
else:
    cash, stocks, cycle = 10000.0, 0, 1

# --- 화면 출력 시작 ---
st.title("🚀 SOXL 동적 퀀트 매매 시스템")

# 차트 출력
show_candle_chart()

# 시장 요약 정보
avg_vol = get_volatility()
curr_p, vwap_p = get_market_summary()

st.divider()
st.subheader(f"📅 주문 예정일: :blue[{trade_date}]")
col1, col2, col3, col4 = st.columns(4)
col1.metric("현재가", f"${curr_p}")
col2.metric("5일 평균 변동폭", f"${avg_vol}")
col3.metric("현재 잔고", f"${cash:,.2f}")
col4.metric("보유 주식수", f"{stocks}주")

# 6. 상훈님의 7000/3000 기반 동적 주문 제안
order_amt = 800.0
proposals = []

if cash >= 7000:
    st.info("💡 **공격 매수 구간** (현금 7,000불 이상)")
    proposals = [
        {'구분': '매수', '가격': vwap_p, '수량': int(order_amt/vwap_p), '비고': 'VWAP 기준'},
        {'구분': '매수', '가격': round(vwap_p - (avg_vol*0.5), 2), '수량': int(order_amt/vwap_p), '비고': '추세 대응'},
        {'구분': '매수', '가격': round(vwap_p - avg_vol, 2), '수량': int(order_amt/vwap_p), '비고': '저점 그물'},
        {'구분': '매도', '가격': round(curr_p * 1.1, 2), '수량': int(stocks*0.3) if stocks>0 else 0, '비고': '익절 대기'}
    ]
elif cash < 3000:
    st.warning("🛡️ **방어 매도 구간** (현금 3,000불 미만)")
    proposals = [
        {'구분': '매도', '가격': round(curr_p * 1.03, 2), '수량': int(stocks/3), '비고': '단기 현금화'},
        {'구분': '매도', '가격': round(curr_p * 1.05, 2), '수량': int(stocks/3), '비고': '안전 수익'},
        {'구분': '매도', '가격': round(curr_p * 1.1, 2), '수량': int(stocks/3), '비고': '목표 익절'},
        {'구분': '매수', '가격': round(vwap_p - avg_vol, 2), '수량': int(order_amt/vwap_p), '비고': '최저가 매수'}
    ]
else:
    st.success("⚖️ **균형 운용 구간**")
    proposals = [
        {'구분': '매수', '가격': vwap_p, '수량': int(order_amt/vwap_p), '비고': '안정 체결'},
        {'구분': '매수', '가격': round(vwap_p - (avg_vol*0.5), 2), '수량': int(order_amt/vwap_p), '비고': '평단 관리'},
        {'구분': '매도', '가격': round(curr_p * 1.05, 2), '수량': int(stocks/2), '비고': '분할 익절'},
        {'구분': '매도', '가격': round(curr_p * 1.1, 2), '수량': int(stocks/2), '비고': '잔량 익절'}
    ]

# 7. 일체형 주문-체결 입력 폼
with st.form("trading_form"):
    st.write("제안된 주문을 확인하고 실제 체결 내용을 입력하세요.")
    h1, h2, h3, h4, h5, h6 = st.columns([1, 1, 1, 1, 1, 1.5])
    h1.write("**제안구분**"); h2.write("**제안가**"); h3.write("**제안수량**")
    h4.write("**체결체크**"); h5.write("**실제단가**"); h6.write("**실제수량**")
    
    filled_data = []
    for i, p in enumerate(proposals):
        c1, c2, c3, c4, c5, c6 = st.columns([1, 1, 1, 1, 1, 1.5])
        c1.write(f"{p['구분']} ({p['비고']})")
        c2.write(f"${p['가격']}")
        c3.write(f"{p['수량']}주")
        
        is_f = c4.checkbox("체결", key=f"f_{i}")
        act_p = c5.number_input("단가", value=float(p['가격']), key=f"p_{i}", step=0.01, label_visibility="collapsed")
        act_q = c6.number_input("수량", value=int(p['수량']), key=f"q_{i}", step=1, label_visibility="collapsed")
        
        if is_f:
            filled_data.append({'type': p['구분'], 'p_price': p['가격'], 'p_qty': p['수량'], 'act_p': act_p, 'act_q': act_q})

    if st.form_submit_button("📁 체결 내역 시트에 일괄 저장"):
        if not filled_data:
            st.warning("체결 체크된 항목이 없습니다.")
        else:
            temp_cash, temp_stocks = cash, stocks
            for item in filled_data:
                amt = round(item['act_p'] * item['act_q'], 2)
                if item['type'] == '매수':
                    temp_stocks += item['act_q']
                    temp_cash -= amt
                else:
                    temp_stocks -= item['act_q']
                    temp_cash += amt
                
                # 상훈님 요청 12개 컬럼 순서로 저장
                sheet.append_row([
                    trade_date, item['type'], item['p_price'], item['p_qty'],
                    "O", item['act_p'], item['act_q'], amt, 
                    temp_stocks, round(temp_cash, 2), cycle, 0
                ])
            st.success("✅ 저장이 완료되었습니다! 페이지를 새로고침합니다.")
            st.rerun()

# 최근 기록 하단 표시
if all_records:
    st.divider()
    st.subheader("📋 최근 매매 히스토리 (마지막 5건)")
    st.dataframe(pd.DataFrame(all_records).tail(5), use_container_width=True)
