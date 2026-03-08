import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# 1. 환경 설정 및 데이터 로드
st.set_page_config(page_title="라오어 팬딩 시스템 v2.4", layout="wide")

@st.cache_data(ttl=3600)
def get_volatility_data():
    """최근 5일 평균 등락폭(High-Low) 계산"""
    ticker = yf.Ticker("SOXL")
    hist = ticker.history(period="7d") # 주말 포함 7일치
    hist['diff'] = hist['High'] - hist['Low']
    return round(hist['diff'].tail(5).mean(), 2)

@st.cache_data(ttl=60)
def get_market_data():
    ticker = yf.Ticker("SOXL")
    hist = ticker.history(period="1d")
    curr = round(hist['Close'].iloc[-1], 2)
    # VWAP 대용: (고가+저가+종가)/3
    vwap = round((hist['High'].iloc[-1] + hist['Low'].iloc[-1] + hist['Close'].iloc[-1]) / 3, 2)
    return curr, vwap

# 데이터 가져오기
avg_vol = get_volatility_data()
curr_p, vwap_p = get_market_data()

# 2. 구글 시트 연동
try:
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    info = dict(st.secrets["gcp_service_account"])
    info["private_key"] = info["private_key"].replace("\\n", "\n").strip()
    creds = Credentials.from_service_account_info(info, scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open("soxl invest").sheet1
    all_records = sheet.get_all_records()
except Exception as e:
    st.error(f"구글 시트 연결 오류: {e}")
    st.stop()

# 현재 상태 파악 (마지막 행 기준)
if all_records:
    last = all_records[-1]
    cash = float(str(last.get('잔고', 10000)).replace(',', ''))
    stocks = int(last.get('주식수', 0))
else:
    cash, stocks = 10000.0, 0

# 3. 메인 대시보드
st.title("📈 SOXL 동적 자금 관리 시스템")
c1, c2, c3, c4 = st.columns(4)
c1.metric("SOXL 현재가", f"${curr_p}")
c2.metric("5일 평균 변동폭", f"${avg_vol}")
c3.metric("현재 잔고", f"${cash}")
c4.metric("보유 주식수", f"{stocks}주")

# 4. 상훈님의 7000/3000 동적 주문 로직
st.subheader("🤖 오늘의 추천 주문 (Limit VWAP 기반)")
order_amt = 800.0
proposals = []

if cash >= 7000:
    st.info("💡 잔고 넉넉 ($7,000↑) - 공격적 매수 모드")
    proposals.append({'구분': '매수1', '가격': vwap_p, '수량': int(order_amt/vwap_p), '전략': 'VWAP 체결용'})
    proposals.append({'구분': '매수2', '가격': round(vwap_p - (avg_vol * 0.5), 2), '수량': int(order_amt/vwap_p), '전략': '평단가 방어'})
    proposals.append({'구분': '매수3', '가격': round(vwap_p - avg_vol, 2), '수량': int(order_amt/vwap_p), '전략': '폭락 대응'})
    # 매도도 1개 섞어서 순환 유도
    proposals.append({'구분': '매도', '가격': round(curr_p * 1.1, 2), '수량': int(stocks*0.3), '전략': '10% 익절'})

elif cash < 3000:
    st.warning("⚠️ 잔고 부족 ($3,000↓) - 현금 확보 모드")
    proposals.append({'구분': '매도1', '가격': round(curr_p * 1.03, 2), '수량': int(stocks/3), '전략': '단기 현금화'})
    proposals.append({'구분': '매도2', '가격': round(curr_p * 1.05, 2), '수량': int(stocks/3), '전략': '안전 수익'})
    proposals.append({'구분': '매도3', '가격': round(curr_p * 1.07, 2), '수량': int(stocks/3), '전략': '목표 익절'})
    # 매수는 1개만 아주 싸게
    proposals.append({'구분': '매수', '가격': round(vwap_p - avg_vol, 2), '수량': int(order_amt/vwap_p), '전략': '최저가 줍줍'})

else:
    st.success("⚖️ 균형 구간 ($3,000 ~ $7,000) - 안정 운용 모드")
    proposals.append({'구분': '매수1', '가격': vwap_p, '수량': int(order_amt/vwap_p), '전략': '기준가 매수'})
    proposals.append({'구분': '매수2', '가격': round(vwap_p - (avg_vol * 0.5), 2), '수량': int(order_amt/vwap_p), '전략': '추가 하락 대응'})
    proposals.append({'구분': '매도1', '가격': round(curr_p * 1.05, 2), '수량': int(stocks/2), '전략': '분할 익절'})

st.table(pd.DataFrame(proposals))

# 5. 기록 섹션
st.divider()
st.subheader("📝 실제 체결 결과 기록")
with st.form("input_form"):
    col_a, col_b, col_c = st.columns(3)
    f_date = col_a.date_input("날짜")
    f_type = col_b.selectbox("구분", ["매수", "매도"])
    f_fill = col_c.radio("체결여부", ["O", "X"])
    
    col_d, col_e = st.columns(2)
    f_price = col_d.number_input("체결단가", value=curr_p)
    f_qty = col_e.number_input("체결수량", min_value=0)
    
    if st.form_submit_button("시트에 기록"):
        # 여기에 앞서 만든 12개 항목 저장 로직(balance 업데이트 등)을 통합하세요.
        st.write("기록 기능 활성화됨!")
