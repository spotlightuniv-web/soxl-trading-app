import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import pytz

# 1. 페이지 설정 및 스타일
st.set_page_config(page_title="라오어 팬딩 시스템 v2.5", layout="wide")

# 2. 미국 장 개장일 및 시간 계산 (3월 9일 자동 계산 로직)
def get_trading_context():
    tz_et = pytz.timezone('US/Eastern')
    now_et = datetime.now(tz_et)
    
    # 기본 주문 예정일 계산
    order_date = now_et
    # 주말 처리
    if order_date.weekday() == 5: order_date += timedelta(days=2) # 토 -> 월
    elif order_date.weekday() == 6: order_date += timedelta(days=1) # 일 -> 월
    # 장 마감(오후 4시) 이후면 다음 영업일로
    elif now_et.hour >= 16:
        order_date += timedelta(days=1)
        if order_date.weekday() == 5: order_date += timedelta(days=2)
        
    return order_date.strftime('%Y-%m-%d')

target_date = get_trading_context()

# 3. 데이터 로드 (변동성 및 현재가)
@st.cache_data(ttl=3600)
def get_volatility():
    ticker = yf.Ticker("SOXL")
    hist = ticker.history(period="10d")
    hist['diff'] = hist['High'] - hist['Low']
    return round(hist['diff'].tail(5).mean(), 2)

@st.cache_data(ttl=60)
def get_current():
    ticker = yf.Ticker("SOXL")
    hist = ticker.history(period="1d")
    curr = round(hist['Close'].iloc[-1], 2)
    vwap = round((hist['High'].iloc[-1] + hist['Low'].iloc[-1] + hist['Close'].iloc[-1]) / 3, 2)
    return curr, vwap

avg_vol = get_volatility()
curr_p, vwap_p = get_current()

# 4. 구글 시트 연결
try:
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    info = dict(st.secrets["gcp_service_account"])
    info["private_key"] = info["private_key"].replace("\\n", "\n").strip()
    creds = Credentials.from_service_account_info(info, scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open("soxl invest").sheet1
    all_records = sheet.get_all_records()
except Exception as e:
    st.error(f"시트 연결 실패: {e}")
    st.stop()

# 현재 계좌 상태
if all_records:
    last = all_records[-1]
    cash = float(str(last.get('잔고', 10000)).replace(',', ''))
    stocks = int(last.get('주식수', 0))
    cycle = int(last.get('사이클회차', 1))
else:
    cash, stocks, cycle = 10000.0, 0, 1

# 5. 메인 UI
st.title("🤖 SOXL 동적 퀀트 매매 비서")
st.subheader(f"📅 다음 매매 예정일: :blue[{target_date}]")

col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
col_stat1.metric("SOXL 현재가", f"${curr_p}")
col_stat2.metric("5일 평균 변동폭", f"${avg_vol}")
col_stat3.metric("현재 잔고", f"${cash:,.2f}")
col_stat4.metric("보유 수량", f"{stocks}주")

# 6. 동적 주문 제안 (7000/3000 로직)
st.divider()
st.subheader("💡 오늘 밤 예약 주문 가이드")

order_amt = 800.0
proposals = []

if cash >= 7000:
    st.info("🚀 공격적 매수 구간 ($7,000↑)")
    proposals = [
        {'구분': '매수', '가격': vwap_p, '수량': int(order_amt/vwap_p), '비고': 'Limit VWAP'},
        {'구분': '매수', '가격': round(vwap_p - (avg_vol * 0.5), 2), '수량': int(order_amt/(vwap_p*0.95)), '비고': '평단방어'},
        {'구분': '매수', '가격': round(vwap_p - avg_vol, 2), '수량': int(order_amt/(vwap_p*0.9)), '비고': '폭락대응'},
        {'구분': '매도', '가격': round(curr_p * 1.1, 2), '수량': int(stocks*0.3) if stocks > 0 else 0, '비고': '익절대기'}
    ]
elif cash < 3000:
    st.warning("🛡️ 현금 확보 구간 ($3,000↓)")
    proposals = [
        {'구분': '매도', '가격': round(curr_p * 1.03, 2), '수량': int(stocks/3), '비고': '단기현금화'},
        {'구분': '매도', '가격': round(curr_p * 1.05, 2), '수량': int(stocks/3), '비고': '안전수익'},
        {'구분': '매도', '가격': round(curr_p * 1.08, 2), '수량': int(stocks/3), '비고': '목표익절'},
        {'구분': '매수', '가격': round(vwap_p - avg_vol, 2), '수량': int(order_amt/vwap_p), '비고': '저점줍줍'}
    ]
else:
    st.success("⚖️ 균형 운용 구간")
    proposals = [
        {'구분': '매수', '가격': vwap_p, '수량': int(order_amt/vwap_p), '비고': '안정체결'},
        {'구분': '매수', '가격': round(vwap_p - (avg_vol * 0.5), 2), '수량': int(order_amt/vwap_p), '비고': '평단방어'},
        {'구분': '매도', '가격': round(curr_p * 1.05, 2), '수량': int(stocks/2), '비고': '분할익절'},
        {'구분': '매도', '가격': round(curr_p * 1.1, 2), '수량': int(stocks/2), '비고': '잔량익절'}
    ]

# 7. 일체형 체결 입력 폼
with st.form("trading_record"):
    st.write("실제 체결된 항목만 체크하세요. (체결가는 수정 가능)")
    record_data = []
    
    for i, p in enumerate(proposals):
        c1, c2, c3, c4, c5 = st.columns([0.5, 1, 1, 1, 2])
        is_filled = c1.checkbox("체결", key=f"f_{i}")
        c2.write(f"**{p['구분']}**")
        f_price = c3.number_input("단가", value=float(p['가격']), key=f"p_{i}", step=0.01)
        f_qty = c4.number_input("수량", value=int(p['수량']), key=f"q_{i}", min_value=0)
        c5.write(f"_{p['비고']}_")
        
        if is_filled:
            record_data.append({'type': p['구분'], 'price': f_price, 'qty': f_qty})

    submit = st.form_submit_button("✅ 체결 내역 구글 시트에 일괄 저장")

    if submit and record_data:
        temp_cash, temp_stocks = cash, stocks
        
        for item in record_data:
            executed_amt = round(item['price'] * item['qty'], 2)
            if item['type'] == '매수':
                temp_stocks += item['qty']
                temp_cash -= executed_amt
            else:
                temp_stocks -= item['qty']
                temp_cash += executed_amt
            
            # 12개 항목 순서 맞춰 생성
            new_row = [
                target_date, item['type'], proposals[0]['가격'], proposals[0]['수량'],
                "O", item['price'], item['qty'], executed_amt,
                temp_stocks, round(temp_cash, 2), cycle, 0
            ]
            sheet.append_row(new_row)
        
        st.balloons()
        st.success(f"{len(record_data)}건의 기록이 완료되었습니다! 페이지를 새로고침합니다.")
        st.rerun()

# 8. 최근 기록 보기
st.divider()
if all_records:
    st.subheader("📋 최근 매매 히스토리")
    st.dataframe(pd.DataFrame(all_records).tail(10), use_container_width=True)
