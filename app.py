import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
import plotly.graph_objects as go  # 캔들 차트를 위한 라이브러리 추가
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import pytz

# 1. 페이지 설정
st.set_page_config(page_title="라오어 팬딩 시스템 v2.8", layout="wide")

# 2. 미국 장 날짜 계산
def get_trading_date():
    tz_et = pytz.timezone('US/Eastern')
    now_et = datetime.now(tz_et)
    target = now_et
    if now_et.hour >= 16 or now_et.weekday() >= 5:
        days_to_add = 1
        if now_et.weekday() == 4: days_to_add = 3
        elif now_et.weekday() == 5: days_to_add = 2
        target += timedelta(days=days_to_add)
    return target.strftime('%Y-%m-%d')

trade_date = get_trading_date()

# 3. 데이터 로드 함수
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

# 4. 🔥 증권사형 캔들스틱 차트 함수
def show_candle_chart():
    st.subheader("📊 SOXL 실시간 캔들 차트")
    t_frame = st.radio("기간 선택", ["시간단위", "일단위", "주단위", "월단위"], horizontal=True)
    
    params = {
        "시간단위": {"period": "1d", "interval": "15m"}, # 15분봉
        "일단위": {"period": "5d", "interval": "30m"}, # 30분봉
        "주단위": {"period": "1mo", "interval": "1d"}, # 일봉
        "월단위": {"period": "6mo", "interval": "1wk"} # 주봉
    }
    
    ticker = yf.Ticker("SOXL")
    df = ticker.history(**params[t_frame])
    
    # Plotly 캔들스틱 생성
    fig = go.Figure(data=[go.Candlestick(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        increasing_line_color='#FF3232', # 상승 (빨강)
        decreasing_line_color='#0066FF'  # 하락 (파랑)
    )])
    
    fig.update_layout(
        height=500,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_rangeslider_visible=False, # 아래 슬라이더 제거 (깔끔하게)
        template="plotly_white"
    )
    
    st.plotly_chart(fig, use_container_width=True)

# 5. 구글 시트 연결 (기존 로직 유지)
try:
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    info = dict(st.secrets["gcp_service_account"])
    info["private_key"] = info["private_key"].replace("\\n", "\n").strip()
    creds = Credentials.from_service_account_info(info, scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open("soxl invest").sheet1
    all_records = sheet.get_all_records()
except:
    st.error("구글 시트 연결 실패.")
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
st.title("🚀 SOXL 스마트 매매 비서 v2.8")

# 증권사형 차트 섹션
show_candle_chart()

# 요약 정보 및 주문 제안/기록 (기존 v2.7 로직과 동일하게 이어짐)
avg_vol = get_volatility()
curr_p, vwap_p = get_market_summary()

st.divider()
st.subheader(f"📅 주문 예정일: :blue[{trade_date}]")
col1, col2, col3, col4 = st.columns(4)
col1.metric("SOXL 현재가", f"${curr_p}")
col2.metric("5일 평균 변동폭", f"${avg_vol}")
col3.metric("현재 잔고", f"${cash:,.2f}")
col4.metric("보유 주식수", f"{stocks}주")

# [이하 주문 제안 및 입력 폼 로직은 v2.7과 동일]
# (지면상 생략하지만, 실제 코드에는 v2.7의 6, 7, 8번 섹션을 그대로 붙여넣으시면 됩니다.)
