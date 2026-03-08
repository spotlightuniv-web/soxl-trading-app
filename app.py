import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="라오어 팬딩 퀀트 시스템", layout="wide")

# 2. 구글 시트 인증 및 연결 설정
try:
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    info = dict(st.secrets["gcp_service_account"])
    info["private_key"] = info["private_key"].replace("\\n", "\n").strip()
    
    creds = Credentials.from_service_account_info(info, scopes=scope)
    client = gspread.authorize(creds)
    
    spreadsheet = client.open("soxl invest")
    sheet = spreadsheet.sheet1
    st.sidebar.success("✅ 구글 시트 연결 성공!")
except Exception as e:
    st.error(f"❌ 연결 중 오류 발생: {e}")
    st.stop()

# 3. 실시간 시세 조회
@st.cache_data(ttl=60)
def get_current_price():
    ticker = yf.Ticker("SOXL")
    data = ticker.history(period="1d")
    return round(data['Close'].iloc[-1], 2)

curr_p = get_current_price()

# 4. 메인 화면
st.title("📈 라오어 팬딩 퀀트 대시보드")
st.metric("SOXL 현재가", f"${curr_p}")

# 5. 체결 기록 입력 및 자동 계산
st.divider()
left_col, right_col = st.columns([1, 2])

with left_col:
    st.subheader("📝 체결 결과 입력")
    with st.form("trade_form", clear_on_submit=True):
        t_date = st.date_input("일자", datetime.now())
        t_type = st.selectbox("구분", ["매수", "매도"])
        t_price = st.number_input("체결단가 ($)", value=curr_p, step=0.01)
        t_qty = st.number_input("주문수량 (주)", min_value=1, step=1)
        t_category = st.selectbox("주문구분", ["LOC", "지정가", "VWAP", "장중매수"])
        
        submitted = st.form_submit_button("시트에 기록 저장")
        
        if submitted:
            all_records = sheet.get_all_records()
            if all_records:
                last_row = all_records[-1]
                # 상훈님의 시트 헤더 명칭 적용
                prev_stock = int(last_row.get('주식수', 0))
                # '주식금액'을 계좌 잔액(현금)으로 가정하여 계산합니다.
                cash_val = str(last_row.get('주식금액', 10000)).replace('$', '').replace(',', '')
                prev_cash = float(cash_val)
            else:
                prev_stock = 0
                prev_cash = 10000.0 # 초기 자금
            
            if t_type == "매수":
                new_stock = prev_stock + t_qty
                new_cash = prev_cash - (t_price * t_qty)
            else:
                new_stock = prev_stock - t_qty
                new_cash = prev_cash + (t_price * t_qty)
            
            # 상훈님이 정해주신 7개 컬럼 순서대로 행 추가
            new_row = [
                t_date.strftime('%Y-%m-%d'), # 일자
                t_type,                       # 구분
                t_price,                      # 체결단가
                t_qty,                        # 주문수량
                t_category,                   # 주문구분
                new_stock,                    # 주식수
                round(new_cash, 2)            # 주식금액
            ]
            sheet.append_row(new_row)
            st.success("✅ 기록 완료!")
            st.rerun()

with right_col:
    st.subheader("📋 최근 매매 현황")
    data = sheet.get_all_records()
    if data:
        st.dataframe(pd.DataFrame(data).tail(15), use_container_width=True)
