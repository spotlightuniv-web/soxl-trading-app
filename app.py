import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# 1. 페이지 설정 및 시세 조회
st.set_page_config(page_title="라오어 팬딩 시스템 v2.2", layout="wide")

@st.cache_data(ttl=60)
def get_stock_data():
    ticker = yf.Ticker("SOXL")
    hist = ticker.history(period="1d")
    return round(hist['Close'].iloc[-1], 2)

curr_p = get_stock_data()

# 2. 구글 시트 연결 (인증 및 안전한 데이터 로드)
try:
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    info = dict(st.secrets["gcp_service_account"])
    info["private_key"] = info["private_key"].replace("\\n", "\n").strip()
    creds = Credentials.from_service_account_info(info, scopes=scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("soxl invest")
    sheet = spreadsheet.sheet1
    
    # 데이터를 읽어올 때 제목 중복이나 빈 시트 에러 방지
    try:
        all_records = sheet.get_all_records()
    except:
        all_records = []
    st.sidebar.success("✅ 구글 시트 연결 및 데이터 로드 성공!")
except Exception as e:
    st.error(f"❌ 연결 오류: {e}")
    st.stop()

# 3. 메인 화면 (현재가 및 차트)
st.title("📈 SOXL 퀀트 대시보드")
st.metric("SOXL 현재가", f"${curr_p}")
st.line_chart(yf.Ticker("SOXL").history(period="1mo")['Close'])

# 4. 주문 제안 (1만 달러 기준 10% 분할 매수 전략)
st.subheader("🤖 오늘 밤 예약 주문 제안")
buy_p = round(curr_p * 0.98, 2)
prop_qty = int(100 / buy_p) if buy_p > 0 else 0 

proposals = pd.DataFrame([
    {'주문구분': '매수', '주문금액': buy_p, '수량': prop_qty, '비고': '분할 매수'},
    {'주문구분': '매도', '주문금액': round(curr_p * 1.1, 2), '수량': prop_qty, '비고': '10% 익절'}
])
st.table(proposals)

# 5. 체결 기록 및 사이클 정산 🧮
st.divider()
col_in, col_out = st.columns([1, 2])

with col_in:
    st.subheader("📝 체결 결과 기록")
    with st.form("trade_form", clear_on_submit=True):
        t_date = st.date_input("일자", datetime.now())
        t_type = st.selectbox("주문구분", ["매수", "매도"])
        t_filled = st.radio("체결여부", ["O", "X"])
        t_price = st.number_input("실제 체결단가", value=curr_p)
        t_qty = st.number_input("실제 체결수량", min_value=0)
        
        submitted = st.form_submit_button("시트에 기록 저장")
        
        if submitted:
            initial_balance = 10000.0
            if all_records:
                last = all_records[-1]
                p_stock = int(last.get('주식수', 0))
                p_cash = float(str(last.get('잔고', initial_balance)).replace(',', ''))
                p_cycle = int(last.get('사이클회차', 1))
            else:
                p_stock, p_cash, p_cycle = 0, initial_balance, 1
            
            # 실제 체결금액 계산
            executed_amt = round(t_price * t_qty, 2) if t_filled == "O" else 0
            
            # 주식수 및 잔고 업데이트
            if t_type == "매수":
                new_stock = p_stock + t_qty if t_filled == "O" else p_stock
                new_cash = round(p_cash - executed_amt, 2)
            else:
                new_stock = p_stock - t_qty if t_filled == "O" else p_stock
                new_cash = round(p_cash + executed_amt, 2)
            
            # 사이클 수익 정산 (주식수가 0이 되는 순간) 🏁
            cycle_profit = 0
            current_cycle = p_cycle
            if p_stock > 0 and new_stock == 0 and t_filled == "O":
                # 직전 사이클 종료 잔고 탐색
                prev_finish_cash = initial_balance
                for rec in reversed(all_records):
                    if int(rec.get('주식수', -1)) == 0:
                        prev_finish_cash = float(str(rec.get('잔고')).replace(',', ''))
                        break
                cycle_profit = round(new_cash - prev_finish_cash, 2)
                p_cycle += 1 
            
            # 12개 항목 순서대로 저장
            new_row = [
                t_date.strftime('%Y-%m-%d'), t_type, buy_p, prop_qty,
                t_filled, t_price, t_qty, executed_amt,
                new_stock, new_cash, current_cycle, cycle_profit
            ]
            sheet.append_row(new_row)
            st.success(f"✅ {current_cycle}회차 기록이 성공적으로 저장되었습니다!")
            st.rerun()

with col_out:
    st.subheader("📋 매매 히스토리")
    if all_records:
        st.dataframe(pd.DataFrame(all_records).tail(15), use_container_width=True)
    else:
        st.info("아직 기록된 데이터가 없습니다. 첫 기록을 입력해보세요!")
