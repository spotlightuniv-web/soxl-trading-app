import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import pytz

# 1. 페이지 설정 및 테마
st.set_page_config(page_title="라오어 팬딩 시스템 v2.7", layout="wide")

# 2. 미국 시장 날짜 계산 (한국 일요일 -> 미국 월요일 3/9 자동 설정)
def get_trading_date():
    tz_et = pytz.timezone('US/Eastern')
    now_et = datetime.now(tz_et)
    target = now_et
    # 장 마감(16시) 이후거나 주말(토/일)이면 다음 영업일로
    if now_et.hour >= 16 or now_et.weekday() >= 5:
        days_to_add = 1
        if now_et.weekday() == 4: days_to_add = 3 # 금 -> 월
        elif now_et.weekday() == 5: days_to_add = 2 # 토 -> 월
        target += timedelta(days=days_to_add)
    return target.strftime('%Y-%m-%d')

trade_date = get_trading_date()

# 3. 데이터 로드 함수 (캐싱 적용)
@st.cache_data(ttl=3600)
def get_volatility():
    ticker = yf.Ticker("SOXL")
    hist = ticker.history(period="10d")
    return round((hist['High'] - hist['Low']).tail(5).mean(), 2)

@st.cache_data(ttl=60)
def get_market_summary():
    ticker = yf.Ticker("SOXL")
    hist = ticker.history(period="1d")
    curr = round(hist['Close'].iloc[-1], 2)
    vwap = round((hist['High'].iloc[-1] + hist['Low'].iloc[-1] + hist['Close'].iloc[-1]) / 3, 2)
    return curr, vwap

# 4. 상단 멀티 차트 기능
def show_stock_chart():
    st.subheader("📊 SOXL 실시간 차트 분석")
    t_frame = st.radio("기간 선택", ["시간단위", "일단위", "주단위", "월단위"], horizontal=True)
    
    # 선택에 따른 파라미터 설정
    params = {
        "시간단위": {"period": "1d", "interval": "60m"},
        "일단위": {"period": "1d", "interval": "15m"},
        "주단위": {"period": "5d", "interval": "60m"},
        "월단위": {"period": "1mo", "interval": "1d"}
    }
    
    ticker = yf.Ticker("SOXL")
    chart_data = ticker.history(**params[t_frame])
    st.line_chart(chart_data['Close'], use_container_width=True)

# 5. 구글 시트 연결
try:
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    info = dict(st.secrets["gcp_service_account"])
    info["private_key"] = info["private_key"].replace("\\n", "\n").strip()
    creds = Credentials.from_service_account_info(info, scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open("soxl invest").sheet1
    all_records = sheet.get_all_records()
except:
    st.error("구글 시트 연결 실패. secrets 설정을 확인하세요.")
    st.stop()

# 현재 계좌 정보
if all_records:
    last = all_records[-1]
    cash = float(str(last.get('잔고', 10000)).replace(',', ''))
    stocks = int(last.get('주식수', 0))
    cycle = int(last.get('사이클회차', 1))
else:
    cash, stocks, cycle = 10000.0, 0, 1

# --- 메인 화면 시작 ---
st.title("📈 SOXL 동적 매매 비서 v2.7")

# 차트 섹션
show_stock_chart()

# 요약 정보
avg_vol = get_volatility()
curr_p, vwap_p = get_market_summary()

st.divider()
st.subheader(f"📅 주문 예정일: :blue[{trade_date}]")
col1, col2, col3, col4 = st.columns(4)
col1.metric("SOXL 현재가", f"${curr_p}")
col2.metric("5일 평균 변동폭", f"${avg_vol}")
col3.metric("현재 잔고", f"${cash:,.2f}")
col4.metric("보유 주식수", f"{stocks}주")

# 6. 동적 주문 제안 (7000/3000 로직)
order_amt = 800.0
proposals = []

if cash >= 7000:
    st.info("💡 **잔고 넉넉** ($7,000↑) - 공격적 매수 그물 가동")
    proposals = [
        {'구분': '매수', '가격': vwap_p, '수량': int(order_amt/vwap_p), '비고': 'VWAP 중심'},
        {'구분': '매수', '가격': round(vwap_p - (avg_vol*0.5), 2), '수량': int(order_amt/vwap_p), '비고': '추세 대응'},
        {'구분': '매수', '가격': round(vwap_p - avg_vol, 2), '수량': int(order_amt/vwap_p), '비고': '저점 그물'},
        {'구분': '매도', '가격': round(curr_p * 1.1, 2), '수량': int(stocks*0.3), '비고': '익절 대기'}
    ]
elif cash < 3000:
    st.warning("⚠️ **잔고 부족** ($3,000↓) - 현금 확보 및 방어 매도")
    proposals = [
        {'구분': '매도', '가격': round(curr_p * 1.03, 2), '수량': int(stocks/3), '비고': '단기 현금화'},
        {'구분': '매도', '가격': round(curr_p * 1.05, 2), '수량': int(stocks/3), '비고': '안전 수익'},
        {'구분': '매도', '가격': round(curr_p * 1.1, 2), '수량': int(stocks/3), '비고': '목표 익절'},
        {'구분': '매수', '가격': round(vwap_p - avg_vol, 2), '수량': int(order_amt/vwap_p), '비고': '최저가 줍줍'}
    ]
else:
    st.success("⚖️ **안정 구간** ($3,000~$7,000) - 균형 매매 가동")
    proposals = [
        {'구분': '매
