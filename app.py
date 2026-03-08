import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="라오어 팬딩 퀀트 시스템", layout="wide")

# 2. 구글 시트 인증 설정 (보안 에러 해결 로직)
try:
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # Secrets에서 정보를 가져와 줄바꿈(\n) 문자를 올바르게 교정합니다.
    info = dict(st.secrets["gcp_service_account"])
    info["private_key"] = info["private_key"].replace("\\n", "\n").strip()
    
    creds = Credentials.from_service_account_info(info, scopes=scope)
    client = gspread.authorize(creds)
    
    # 상훈님의 시트 열기
    spreadsheet = client.open("soxl invest")
    sheet = spreadsheet.sheet1
    st.sidebar.success("✅ 구글 시트 연결 성공!")
except Exception as e:
    st.error(f"❌ 연결 실패: {e}")
    st.stop()

# 3. 실시간 시세 데이터 가져오기
@st.cache_data(ttl=60) # 1분마다 갱신
def get_stock_data():
    ticker = yf.Ticker("SOXL")
    hist = ticker.history(period="1d")
    return round(hist['Close'].iloc[-1], 2)

curr_p = get_stock_data()

# 4. 대시보드 상단 현황
st.title("📈 라오어 팬딩 퀀트 대시보드")
col1, col2, col3 = st.columns(3)
col1.metric("SOXL 현재가", f"${curr_p}")

# 5. 주문 제안 (상훈님의 가이드 방식 반영)
st.subheader("📢 오늘 밤 예약 주문 제안")
prop_data = [
    {'순번': '1-1', '구분': '매수', '예약가': round(curr_p * 0.98, 2), '수량': 15, '비고': 'Limit VWAP -2%'},
    {'순번': '2-1', '구분': '매도', '예약가': round(curr_p * 1.05, 2), '수량': 15, '비고': '익절 목표 +5%'},
]
st.table(pd.DataFrame(prop_data))

# 6. 체결 기록 및 자동 계산 로직
st.divider()
left_col, right_col = st.columns([1, 2])

with left_col:
    st.subheader("📝 체결 결과 입력")
    with st.form("trade_form", clear_on_submit=True):
        t_date = st.date_input("체결 일자", datetime.now())
        t_type = st.selectbox("구분", ["매수", "매도"])
        t_price = st.number_input("체결 단가 ($)", value=curr_p, step=0.01)
        t_qty = st.number_input("체결 수량 (주)", min_value=1, step=1)
        
        submitted = st.form_submit_button("구글 시트에 기록하기")
        
        if submitted:
            # 기존 마지막 데이터 가져오기 (잔고 계산용)
