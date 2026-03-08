import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# 1. 페이지 설정 및 시세 데이터 조회 📊
st.set_page_config(page_title="라오어 팬딩 시스템 v2.1", layout="wide")

@st.cache_data(ttl=60)
def get_stock_data():
    ticker = yf.Ticker("SOXL")
    hist = ticker.history(period="1d")
    return round(hist['Close'].iloc[-1], 2)

curr_p = get_stock_data()

# 2. 구글 시트 연결 (Secrets 설정 활용) 🔑
try:
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    info = dict(st.secrets["gcp_service_account"])
    info["private_key"] = info["private_key"].replace("\\n", "\n").strip()
    creds = Credentials.from_service_account_info(info, scopes=scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("soxl invest")
    sheet = spreadsheet.sheet1
except:
    st.error("구글 시트 연결 실패! Secrets 설정을 확인해주세요.")
    st.stop()

# 3. 대시보드 상단 (현재가 및 차트) 📉
st.title("🚀 SOXL 퀀트 대시보드")
st.metric("SOXL 현재가", f"${curr_p}")
st.line_chart(yf.Ticker("SOXL").history(period="1mo")['Close'])

# 4. 주문 제안 (1만 달러 기준, 약 10% 분할 매수) 🤖
st.subheader("💡 오늘 밤 예약 주문 제안")
buy_p = round(curr_p * 0.98, 2)
# 하루치 매수량 (약 100달러 규모로 설정하여 10분할 예시)
prop_qty = int(100 / buy_p) if buy_p > 0 else 0 

proposals = pd.DataFrame([
    {'주문구분': '매수', '주문금액': buy_p, '수량': prop_qty, '비고': '분할 매수'},
    {'주문구분': '매도', '주문금액': round(curr_p * 1.1, 2), '수량': prop_qty, '비고': '10% 익절'}
])
st.table(proposals)

# 5. 체결 기록 및 사이클 정산 로직 🧮
st.divider()
col_in, col_out = st.columns([1, 2])

with col_in:
    st.subheader("📝 체결 결과 기록")
    with st.form("trade_form", clear_on_submit=True):
        t_date = st.date_input("일자", datetime.now())
        t_type = st.selectbox("주문구분", ["매수", "매도"])
        t_filled = st.radio("체결여부", ["O", "X"])
        t_price = st.number_input("체결단가", value=curr_p)
        t_qty = st.number_input("주문수량", min_value=0)
        
        submitted = st.form_submit_button("시트에 기록 저장")
        
        if submitted:
            all_records = sheet.get_all_records()
            initial_balance = 10000.0
            
            if all_records:
                last = all_records[-1]
                p_stock = int(last.get('주식수', 0))
                p_cash = float(str(last.get('잔고', initial_balance)).replace(',', ''))
                p_cycle = int(last.get('사이클회차', 1))
            else:
                p_stock, p_cash, p_cycle = 0, initial_balance, 1
            
            # 실제 체결액 계산
            executed_amt = t_price * t_qty if t_filled == "O" else 0
            
            # 주식수 및 현금 잔고 업데이트
            if t_type == "매수":
                new_stock = p_stock + t_qty if t_filled == "O" else p_stock
                new_cash = p_cash - executed_amt
            else:
                new_stock = p_stock - t_qty if t_filled == "O" else p_stock
                new_cash = p_cash + executed_amt
            
            # 사이클 수익 계산 (주식수가 0이 되는 순간) 🏁
            cycle_profit = 0
            if p_stock > 0 and new_stock == 0 and t_filled == "O":
                # 이전 사이클의 종료 금액 찾기
                prev_finish_balance = initial_balance
                for rec in reversed(all_records[:-1]): # 마지막 행 제외하고 역순 탐색
                    if int(rec.get('주식수', -1)) == 0:
                        prev_finish_balance = float(str(rec.get('잔고')).replace(',', ''))
                        break
                cycle_profit = new_cash - prev_finish_balance
                p_cycle += 1 # 주식수가 0이 되었으므로 다음 입력부터는 다음 회차
            
            # 시트 행 추가 (상훈님이 정하신 12개 항목 순서)
            new_row = [
                t_date.strftime('%Y-%m-%d'), t_type, buy_p, prop_qty,
                t_filled, t_price, t_qty, round(executed_amt, 2),
                new_stock, round(new_cash, 2), p_cycle, round(cycle_profit, 2)
            ]
            sheet.append_row(new_row)
            st.success(f"✅ {p_cycle}회차 기록 완료!")
            st.rerun()

with col_out:
    st.subheader("📋 매매 히스토리")
    data = sheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df.tail(15), use_container_width=True)
