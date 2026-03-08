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
    
    # Secrets에서 정보를 가져와 딕셔너리로 변환합니다.
    info = dict(st.secrets["gcp_service_account"])
    
    # PEM 파일 로드 에러를 방지하기 위해 키 내부의 줄바꿈을 강제로 교정합니다.
    # 만약 Secrets에 이미 줄바꿈이 되어 있어도 이 코드가 안전하게 처리합니다.
    info["private_key"] = info["private_key"].replace("\\n", "\n").strip()
    
    creds = Credentials.from_service_account_info(info, scopes=scope)
    client = gspread.authorize(creds)
    
    # 상훈님의 시트 이름으로 연결합니다.
    spreadsheet = client.open("soxl invest")
    sheet = spreadsheet.sheet1
    st.sidebar.success("✅ 구글 시트 연결 성공!")
except Exception as e:
    st.error(f"❌ 구글 시트 연결 중 오류 발생: {e}")
    st.info("💡 Tip: Secrets 설정에서 private_key가 따옴표 3개(\"\"\")로 잘 감싸져 있는지 확인해 주세요.")
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

# 5. 주문 제안 (라오어 가이드 기반 예시)
st.subheader("📢 오늘 밤 예약 주문 제안")
proposals = [
    {'순번': '1-1', '구분': '매수', '예약가': round(curr_p * 0.98, 2), '수량': 15, '상태': '대기'},
    {'순번': '2-1', '구분': '매도', '예약가': round(curr_p * 1.05, 2), '수량': 15, '상태': '대기'}
]
st.table(pd.DataFrame(proposals))

# 6. 체결 기록 입력 및 잔고 자동 계산
st.divider()
left_col, right_col = st.columns([1, 2])

with left_col:
    st.subheader("📝 체결 결과 수기 입력")
    with st.form("trade_form", clear_on_submit=True):
        t_date = st.date_input("체결 일자", datetime.now())
        t_type = st.selectbox("구분", ["매수", "매도"])
        t_price = st.number_input("체결 단가 ($)", value=curr_p, step=0.01)
        t_qty = st.number_input("체결 수량 (주)", min_value=1, step=1)
        
        submitted = st.form_submit_button("시트에 기록 저장")
        
        if submitted:
            # 시트의 기존 데이터를 읽어와서 잔고를 추적합니다.
            all_records = sheet.get_all_records()
            if all_records:
                last_row = all_records[-1]
                # '주식수'와 '계좌금액' 컬럼명을 상훈님의 시트 헤더와 일치시킵니다.
                prev_stock = int(last_row.get('주식수', 0))
                # 달러 표시나 콤마가 있을 경우를 대비해 숫자로 변환합니다.
                cash_val = str(last_row.get('계좌금액', 10000)).replace('$', '').replace(',', '')
                prev_cash = float(cash_val)
            else:
                prev_stock = 0
                prev_cash = 10000.0 # 초기 자금
            
            # 매수/매도 로직 계산
            amount = t_price * t_qty
            if t_type == "매수":
                new_stock = prev_stock + t_qty
                new_cash = prev_cash - amount
            else:
                new_stock = prev_stock - t_qty
                new_cash = prev_cash + amount
            
            # 구글 시트에 새로운 행 추가
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
            st.success("✅ 구글 시트에 데이터가 성공적으로 저장되었습니다!")
            st.rerun()

# 7. 최근 매매 기록 표시
with right_col:
    st.subheader("📋 실시간 매매 기록 (최근 15건)")
    data = sheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df.tail(15), use_container_width=True)
    else:
        st.info("시트에 아직 기록된 데이터가 없습니다.")
