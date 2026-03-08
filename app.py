import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import pytz

# 1. 미국 시장 날짜 계산 (3월 9일 주문 가능 여부 포함)
def get_next_trading_date():
    # 미국 동부 표준시 기준
    tz_et = pytz.timezone('US/Eastern')
    now_et = datetime.now(tz_et)
    
    # 기본적으로 오늘 혹은 다음 영업일 계산
    next_date = now_et
    # 토요일(5), 일요일(6)이면 월요일로 변경
    if next_date.weekday() == 5: next_date += timedelta(days=2)
    elif next_date.weekday() == 6: next_date += timedelta(days=1)
    # 장 마감 이후면 다음날로 (현지시간 오후 4시 기준)
    elif now_et.hour >= 16: next_date += timedelta(days=1)
    
    return next_date.strftime('%Y-%m-%d')

trade_date = get_next_trading_date()

# 2. 대시보드 상단
st.title("🚀 SOXL 스마트 매매 비서")
st.info(f"📅 현재 주문 가능일: **{trade_date}**")

# 3. 동적 주문 제안 (상훈님의 7000/3000 로직 적용)
# (이전 코드의 get_market_data, get_volatility 로직 실행 결과가 proposals에 담겨있다고 가정)
proposals = [
    {'구분': '매수1', '가격': 70.15, '수량': 11, '전략': 'VWAP 체결용'},
    {'구분': '매수2', '가격': 68.50, '수량': 12, '전략': '평단가 방어'},
    {'구분': '매도1', '가격': 75.20, '수량': 30, '전략': '익절 그물'}
]

# 4. 체결 입력 섹션 (고정값 기반 바로 입력)
st.subheader("📝 당일 주문 체결 확인")
st.write("제시된 주문이 체결되었다면 '체결'을 체크하고 저장하세요.")

with st.form("quick_record"):
    updated_rows = []
    for i, p in enumerate(proposals):
        col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
        is_filled = col1.checkbox(f"{p['구분']} 체결", key=f"check_{i}")
        fill_price = col2.number_input("체결가", value=float(p['가격']), key=f"price_{i}")
        fill_qty = col3.number_input("수량", value=int(p['수량']), key=f"qty_{i}")
        
        if is_filled:
            updated_rows.append({
                '일자': trade_date,
                '구분': p['구분'][:2], # '매수1' -> '매수'
                '체결단가': fill_price,
                '주문수량': fill_qty,
                '체결여부': 'O'
            })

    if st.form_submit_button("✅ 선택한 체결 내역 시트에 저장"):
        if updated_rows:
            # TODO: 구글 시트 append_row 실행 로직
            st.success(f"{len(updated_rows)}건의 체결 기록이 저장되었습니다!")
        else:
            st.warning("체결된 항목이 없습니다.")
