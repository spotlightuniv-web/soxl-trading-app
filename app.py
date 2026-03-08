import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="라오어 팬딩 퀀트 시스템", layout="wide")

# --- [데이터 관리] 임시 데이터베이스 (나중에 구글 시트로 연결) ---
if 'trade_log' not in st.session_state:
    st.session_state.trade_log = pd.DataFrame(columns=[
        '일자', '구분', '체결단가', '주문수량', '주문금액', '주식수', '계좌금액'
    ])

# --- [상단] 실시간 시세 및 자산 현황 ---
st.title("📊 라오어 팬딩 퀀트 대시보드")
data = yf.Ticker("SOXL").history(period="1d")
curr_p = round(data['Close'].iloc[-1], 2)

col1, col2, col3 = st.columns(3)
col1.metric("SOXL 현재가", f"${curr_p}")
col2.metric("현재 사이클", "1회차")
col3.metric("목표 수익률", "40.0%")

# --- [중단] 주문 제안 표 (상훈님의 퀀트 로직 반영) ---
st.subheader("📢 오늘의 예약 주문 제안 (Limit VWAP)")
# 상훈님의 표 양식을 참고한 제안가 계산
prop_data = [
    {'순번': '1-1', '구분': '매수', '예약가': round(curr_p * 0.98, 2), '수량': 14},
    {'순번': '1-2', '구분': '매수', '예약가': round(curr_p * 0.96, 2), '수량': 14},
    {'순번': '2-1', '구분': '매도', '예약가': round(curr_p * 1.05, 2), '수량': 14},
]
st.table(pd.DataFrame(prop_data))

# --- [하단 왼쪽] 실 체결 데이터 수기 입력 ---
st.divider()
left_col, right_col = st.columns([1, 2])

with left_col:
    st.subheader("📝 실 체결 결과 입력")
    with st.form("trade_form", clear_on_submit=True):
        t_date = st.date_input("체결 일자", datetime.now())
        t_type = st.selectbox("주문 구분", ["매수", "매도"])
        t_price = st.number_input("실제 체결 단가 ($)", value=curr_p, step=0.01)
        t_qty = st.number_input("실제 체결 수량 (주)", value=0, step=1)
        
        submitted = st.form_submit_button("체결 기록 저장")
        
        if submitted and t_qty > 0:
            # 신규 데이터 생성 (상훈님 엑셀 양식 기반 계산)
            new_data = {
                '일자': t_date.strftime('%Y-%m-%d'),
                '구분': t_type,
                '체결단가': t_price,
                '주문수량': t_qty,
                '주문금액': round(t_price * t_qty, 2),
                '주식수': 0, # 로직 추가 예정
                '계좌금액': 0 # 로직 추가 예정
            }
            st.session_state.trade_log = pd.concat([st.session_state.trade_log, pd.DataFrame([new_data])], ignore_index=True)
            st.success(f"{t_date} {t_type} 기록이 추가되었습니다.")

# --- [하단 오른쪽] 라오어 팬딩 스타일 기록 표 ---
with right_col:
    st.subheader("📋 퀀트 전략 매매 기록 (라오어 팬딩 양식)")
    if not st.session_state.trade_log.empty:
        st.dataframe(st.session_state.trade_log, use_container_width=True)
    else:
        st.info("아직 기록된 체결 내역이 없습니다. 왼쪽에서 입력해 주세요.")
