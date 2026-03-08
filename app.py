import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

# 웹 화면 구성
st.set_page_config(page_title="상훈 SOXL 시스템", layout="wide")

st.title("📈 상훈 SOXL 자동매매 시스템")

# 사이드바 설정 (배수 등)
with st.sidebar:
    st.header("⚙️ 설정")
    leverage = st.number_input("운용 배수", min_value=1, max_value=5, value=3)
    initial_seed = 10000
    st.write(f"총 운용 자산: ${initial_seed * leverage:,}")

# 메인 화면 - 시세 조회 (간단 버전)
data = yf.Ticker("SOXL").history(period="1d")
curr_p = round(data['Close'].iloc[-1], 2)

col1, col2, col3 = st.columns(3)
col1.metric("현재가", f"${curr_p}")
col2.metric("수익률", "0.00%", "+1.2%")
col3.metric("사이클", "1회차")

# 주문 제안 표
st.subheader("📢 오늘 밤 주문 제안")
proposals = [
    {'구분': '매수(VWAP)', '가격': curr_p, '수량': 10},
    {'구분': '매도(익절)', '가격': round(curr_p * 1.03, 2), '수량': 5}
]
st.table(pd.DataFrame(proposals))

# 차트
st.subheader("📊 SOXL 최근 흐름")
history = yf.download("SOXL", period="5d", interval="15m")
st.line_chart(history['Close'])

# 체결 입력 폼
st.subheader("📝 체결 결과 기록")
with st.form("trade_form"):
    t_type = st.selectbox("유형", ["매수", "매도"])
    t_price = st.number_input("체결가", value=curr_p)
    t_qty = st.number_input("수량", value=1)
    submitted = st.form_submit_button("기록하기")
    if submitted:
        st.success(f"{t_type} 기록 완료! (서버 연동은 다음 단계에서)")
