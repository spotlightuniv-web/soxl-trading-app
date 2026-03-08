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
    
    # Secrets에서 정보를 가져와 딕셔너리로 변환
    info = dict(st.secrets["gcp_service_account"])
    
    # [핵심] 텍스트 내의 \n 글자를 진짜 줄바꿈(엔터) 신호로 강제 교체합니다 🪄
    info["private_key"] = info["private_key"].replace("\\n", "\n")
    
    creds = Credentials.from_service_account_info(info, scopes=scope)
    client = gspread.authorize(creds)
    
    # 상훈님의 시트 이름 확인 ("soxl invest")
    spreadsheet = client.open("soxl invest")
    sheet = spreadsheet.sheet1
    st.sidebar.success("✅ 드디어 구글 시트 연결 성공!")
except Exception as e:
    st.error(f"❌ 연결 중 오류 발생: {e}")
    st.info("💡 만약 'InvalidLength' 에러가 여전하다면 Secrets의 private_key 값이 따옴표 3개(\"\"\")로 감싸졌는지 확인해 주세요.")
    st.stop()

# 3. 실시간 시세 조회 함수
@st.cache_data(ttl=60)
def get_current_price():
    ticker = yf.Ticker("SOXL")
    data = ticker.history(period="1d")
    return round(data['Close'].iloc[-1], 2)

curr_p = get_current_price()

# 4. 메인 화면 대시보드
st.title("📈 라오어 팬딩 퀀트 대시보드")
col1, col2, col3 = st.columns(3)
col1.metric("SOXL 현재가", f"${curr_p}")

# 5. 주문 제안 (예시 전략)
st.subheader("📢 오늘 밤 예약 주문 제안")
proposals = [
    {'순번': '1-1', '구분': '매수', '예약가': round(curr_p * 0.98, 2), '수량': 15},
    {'순번': '2-1', '구분': '매도', '예약가': round(curr_p * 1.05, 2), '수량': 15}
]
st.table(pd.DataFrame(proposals))

# 6. 체결 기록 입력 및 자동 계산
st.divider()
left_col, right_col = st.columns([1, 2])

with left_col:
    st.subheader("📝 체결 결과 기록")
    with st.form("trade_form", clear_on_submit=True):
        t_date = st.date_input("체결 일자", datetime.now())
        t_type = st.selectbox("구분", ["매수", "매도"])
        t_price = st.number_input("체결 단가 ($)", value=curr_p, step=0.01)
        t_qty = st.number_input("체결 수량 (주)", min_value=1, step=1)
        
        submitted = st.form_submit_button("기록 저장하기")
        
        if submitted:
            # 기존 데이터 읽어와서 잔고 계산
            all_records = sheet.get_all_records()
            if all_records:
                last_row = all_records[-1]
                prev_stock = int(last_row.get('주식수', 0))
                cash_raw = str(last_row.get('계좌금액', 10000)).replace('$', '').replace(',', '')
                prev_cash = float(cash_raw)
            else:
                prev_stock = 0
                prev_cash = 10000.0
            
            # 매수/매도 로직 계산
            amount = t_price * t_qty
            if t_type == "매수":
                new_stock = prev_stock + t_qty
                new_cash = prev_cash - amount
            else:
                new_stock = prev_stock - t_qty
                new_cash = prev_cash + amount
            
            # 구글 시트에 행 추가
            new_row = [
                t_date.strftime('%Y-%m-%d'),
                t_type,
                t_price,
                t_qty,
                round(amount, 2),
                new_stock,
                round(new_cash, 2)
            ]
            sheet.append_row(new_row)
            st.success("✅ 기록 완료!")
            st.rerun()

# 7. 매매 기록 표시
with right_col:
    st.subheader("📋 최근 매매 현황")
    data = sheet.get_all_records()
    if data:
        st.dataframe(pd.DataFrame(data).tail(10), use_container_width=True)
