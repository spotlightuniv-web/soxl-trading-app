import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import pytz

# 1. 페이지 설정
st.set_page_config(page_title="라오어 팬딩 시스템 v2.6", layout="wide")

# 2. 미국 장 날짜 계산 (미국 시간 기준 다음 영업일)
def get_trading_date():
    tz_et = pytz.timezone('US/Eastern')
    now_et = datetime.now(tz_et)
    target = now_et
    # 오후 4시 이후거나 주말이면 다음 영업일로
    if now_et.hour >= 16 or now_et.weekday() >= 5:
        days_to_add = 1
        if now_et.weekday() == 4: days_to_add = 3 # 금 -> 월
        elif now_et.weekday() == 5: days_to_add = 2 # 토 -> 월
        target += timedelta(days=days_to_add)
    return target.strftime('%Y-%m-%d')

trade_date = get_trading_date()

# 3. 시장 데이터 가져오기
@st.cache_data(ttl=3600)
def fetch_volatility():
    hist = yf.Ticker("SOXL").history(period="10d")
    return round((hist['High'] - hist['Low']).tail(5).mean(), 2)

@st.cache_data(ttl=60)
def fetch_market():
    ticker = yf.Ticker("SOXL")
    hist = ticker.history(period="1d")
    curr = round(hist['Close'].iloc[-1], 2)
    vwap = round((hist['High'].iloc[-1] + hist['Low'].iloc[-1] + hist['Close'].iloc[-1]) / 3, 2)
    return curr, vwap

avg_vol = fetch_volatility()
curr_p, vwap_p = fetch_market()

# 4. 구글 시트 연동
try:
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    info = dict(st.secrets["gcp_service_account"])
    info["private_key"] = info["private_key"].replace("\\n", "\n").strip()
    creds = Credentials.from_service_account_info(info, scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open("soxl invest").sheet1
    all_records = sheet.get_all_records()
except:
    st.error("구글 시트 연결 실패")
    st.stop()

# 계좌 상태 정보
if all_records:
    last = all_records[-1]
    cash = float(str(last.get('잔고', 10000)).replace(',', ''))
    stocks = int(last.get('주식수', 0))
    cycle = int(last.get('사이클회차', 1))
else:
    cash, stocks, cycle = 10000.0, 0, 1

# 5. UI 상단
st.title("📈 SOXL 동적 매매 시스템")
st.write(f"📅 주문 예정일: **{trade_date}** | 5일 변동폭: **${avg_vol}**")

col_a, col_b = st.columns(2)
col_a.metric("현재가", f"${curr_p}")
col_b.metric("잔고/주식수", f"${cash:,.2f} / {stocks}주")

# 6. 주문 제안 로직 (7000/3000 기준)
st.divider()
st.subheader("🤖 주문 가이드 및 체결 입력")

order_amt = 800.0
proposals = []

if cash >= 7000:
    proposals = [
        {'구분': '매수', '가격': vwap_p, '수량': int(order_amt/vwap_p), '비고': 'VWAP 기준'},
        {'구분': '매수', '가격': round(vwap_p - (avg_vol*0.5), 2), '수량': int(order_amt/vwap_p), '비고': '추세 대응'},
        {'구분': '매수', '가격': round(vwap_p - avg_vol, 2), '수량': int(order_amt/vwap_p), '비고': '저점 그물'},
        {'구분': '매도', '가격': round(curr_p * 1.1, 2), '수량': int(stocks*0.3), '비고': '수익 대기'}
    ]
elif cash < 3000:
    proposals = [
        {'구분': '매도', '가격': round(curr_p * 1.03, 2), '수량': int(stocks/3), '비고': '현금 확보'},
        {'구분': '매도', '가격': round(curr_p * 1.05, 2), '수량': int(stocks/3), '비고': '안전 수익'},
        {'구분': '매도', '가격': round(curr_p * 1.1, 2), '수량': int(stocks/3), '비고': '목표 익절'},
        {'구분': '매수', '가격': round(vwap_p - avg_vol, 2), '수량': int(order_amt/vwap_p), '비고': '최저가 매수'}
    ]
else:
    proposals = [
        {'구분': '매수', '가격': vwap_p, '수량': int(order_amt/vwap_p), '비고': '균형 매수'},
        {'구분': '매수', '가격': round(vwap_p - (avg_vol*0.5), 2), '수량': int(order_amt/vwap_p), '비고': '평단 관리'},
        {'구분': '매도', '가격': round(curr_p * 1.05, 2), '수량': int(stocks/2), '비고': '분할 익절'},
        {'구분': '매도', '가격': round(curr_p * 1.1, 2), '수량': int(stocks/2), '비고': '잔량 익절'}
    ]

# 7. 일체형 입력 테이블
with st.form("trade_input"):
    # 헤더
    h1, h2, h3, h4, h5, h6 = st.columns([1, 1, 1, 1, 1, 1.5])
    h1.write("**제안 구분**")
    h2.write("**제안 단가**")
    h3.write("**제안 수량**")
    h4.write("**체결 여부**")
    h5.write("**실제 단가**")
    h6.write("**실제 수량**")
    
    records = []
    for i, p in enumerate(proposals):
        c1, c2, c3, c4, c5, c6 = st.columns([1, 1, 1, 1, 1, 1.5])
        c1.write(f"{p['구분']} ({p['비고']})")
        c2.write(f"${p['가격']}")
        c3.write(f"{p['수량']}주")
        
        filled = c4.checkbox("체결됨", key=f"f_{i}")
        actual_p = c5.number_input("단가", value=float(p['가격']), key=f"ap_{i}", label_visibility="collapsed")
        actual_q = c6.number_input("수량", value=int(p['수량']), key=f"aq_{i}", label_visibility="collapsed")
        
        if filled:
            records.append({'p': p, 'act_p': actual_p, 'act_q': actual_q})

    if st.form_submit_button("📁 체결 기록 시트에 저장"):
        if not records:
            st.warning("체결된 항목이 없습니다.")
        else:
            temp_cash, temp_stocks = cash, stocks
            for item in records:
                p = item['p']
                act_p, act_q = item['act_p'], item['act_q']
                exec_amt = round(act_p * act_q, 2)
                
                if p['구분'] == '매수':
                    temp_stocks += act_q
                    temp_cash -= exec_amt
                else:
                    temp_stocks -= act_q
                    temp_cash += exec_amt
                
                # 상훈님 요청 12개 컬럼 순서
                # 일자, 구분, 제안가, 제안수량, 여부, 체결가, 체결수량, 체결액, 주식수, 잔고, 회차, 수익
                row = [
                    trade_date, p['구분'], p['가격'], p['수량'],
                    "O", act_p, act_q, exec_amt,
                    temp_stocks, round(temp_cash, 2), cycle, 0
                ]
                sheet.append_row(row)
            
            st.success("✅ 저장 완료! 페이지를 새로고침합니다.")
            st.rerun()

# 8. 히스토리
if all_records:
    st.divider()
    st.subheader("📋 최근 기록")
    st.dataframe(pd.DataFrame(all_records).tail(5), use_container_width=True)
