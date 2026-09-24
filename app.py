import streamlit as st
import pandas as pd
import plotly.express as px
import re
from datetime import datetime

# ----------------------------------------------------
# 1. 모바일 친화적 페이지 설정
# ----------------------------------------------------
st.set_page_config(
    page_title="조정부 9월 챌린지",
    page_icon="🚣",
    layout="centered",
    initial_sidebar_state="collapsed"
)

CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQKSCkdKmmNi07nmmO5RN6vDmt_dobOqdCpluVAoP-91dyu36nyuMjuXJXMXrzQDquOq9seEpHtN5_6/pub?gid=995447885&single=true&output=csv"
TARGET_METERS = 50000

def extract_drive_image_urls(raw_text):
    if pd.isna(raw_text): return []
    urls = [u.strip() for u in str(raw_text).split(',') if u.strip()]
    direct_urls = []
    for url in urls:
        match_id = re.search(r'id=([a-zA-Z0-9_-]+)', url)
        match_d = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
        file_id = match_id.group(1) if match_id else (match_d.group(1) if match_d else None)
        if file_id: direct_urls.append(f"https://lh3.googleusercontent.com/d/{file_id}")
    return direct_urls

@st.cache_data(ttl=30)
def load_data():
    raw_df = pd.read_csv(CSV_URL)
    expected_cols = ["날짜", "이름", "총거리", "운동종류", "사진링크", "구분", "메모"]
    rename_dict = {raw_df.columns[i]: expected_cols[i] for i in range(min(len(raw_df.columns), len(expected_cols)))}
    df = raw_df.rename(columns=rename_dict)
    
    # 💡 [핵심 해결] 숫자만 순서대로 추출하여 강제로 날짜를 만드는 무적의 파서 적용
    def parse_strict_date(val):
        if pd.isna(val): return pd.NaT
        s = str(val).strip()
        
        # 1. 엑셀 숫자 형태 (시리얼 넘버) 처리
        if s.replace('.', '', 1).isdigit():
            try: return pd.to_datetime(float(s), unit='D', origin='1899-12-30')
            except: pass
            
        # 2. 텍스트 안에서 숫자만 모두 뽑아내기 (년, 월, 일, 시, 분, 초 순서)
        nums = re.findall(r'\d+', s)
        if len(nums) >= 3:
            try:
                y, m, d = int(nums[0]), int(nums[1]), int(nums[2])
                
                # 년도가 2자리로 들어올 경우 (예: 26년 -> 2026년)
                if y < 100: y += 2000 
                
                if len(nums) >= 5:
                    hh, mm = int(nums[3]), int(nums[4])
                    ss = int(nums[5]) if len(nums) >= 6 else 0
                    
                    # 오후(PM) / 오전(AM) 시간 보정
                    s_upper = s.upper()
                    if ('오후' in s or 'PM' in s_upper) and hh < 12:
                        hh += 12
                    elif ('오전' in s or 'AM' in s_upper) and hh == 12:
                        hh = 0
                        
                    return pd.Timestamp(year=y, month=m, day=d, hour=hh, minute=mm, second=ss)
                else:
                    return pd.Timestamp(year=y, month=m, day=d)
            except: pass
            
        # 3. 위 방식이 모두 실패하면 판다스 기본 기능으로 시도
        return pd.to_datetime(s, errors='coerce')

    df['날짜'] = df['날짜'].apply(parse_strict_date)
    df = df.dropna(subset=['이름'])
    
    if '총거리' in df.columns:
        df['총거리'] = pd.to_numeric(df['총거리'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    else: df['총거리'] = 0
        
    df['페이스(초)'] = None
    if '사진링크' not in df.columns: df['사진링크'] = ""
    if '구분' not in df.columns: df['구분'] = "기존"
    if '운동종류' not in df.columns: df['운동종류'] = "운동"
    if '메모' not in df.columns: df['메모'] = ""
    
    # 💡 강서윤 부원의 구분을 강제로 '신입'으로 변경
    df.loc[df['이름'].astype(str).str.replace(' ', '') == '강서윤', '구분'] = '신입'
    
    return df

try:
    df = load_data()
    # 💡 신입 부원(강서윤 등)을 제외하고 '기존' 부원 데이터만 표시하도록 필터링
    df = df[df['구분'] == '기존'] 
except:
    st.error("데이터 로딩 오류")
    st.stop()

# ----------------------------------------------------
# 헤더 영역
# ----------------------------------------------------
st.markdown("<h1 style='text-align: center;'>🚣‍♀️ 9월 운동인증 챌린지</h1>", unsafe_allow_html=True)
st.caption("<p style='text-align: center;'>One team, one spirit.</p>", unsafe_allow_html=True)
st.divider()

if df.empty:
    st.info("아직 등록된 기록이 없습니다. 첫 인증의 주인공이 되어보세요!")
    st.stop()

# ----------------------------------------------------
# 메인 탭(Tab) UI 구성
# ----------------------------------------------------
tab1, tab2, tab3 = st.tabs(["🏆 랭킹 보드", "👤 내 기록실", "📸 갤러리"])

# 데이터 사전 계산 (추첨권 로직)
ticket_df = df.groupby('이름').agg(참여횟수=('날짜', 'count'), 총거리=('총거리', 'sum')).reset_index()
ticket_df['기본추첨권'] = ticket_df['참여횟수']
ticket_df['보너스추첨권'] = ticket_df['총거리'].apply(lambda x: 3 if x >= TARGET_METERS else 0)
ticket_df['총추첨권'] = ticket_df['기본추첨권'] + ticket_df['보너스추첨권']

# ==========================================
# 탭 1: 랭킹 보드 (명예의 전당)
# ==========================================
with tab1:
    st.subheader("🔥 명예의 전당")
    
    # 1) 추첨권 Top 3
    st.markdown("##### 🎟️ 추첨권 획득 순위")
    ticket_rank = ticket_df.sort_values(by=['총추첨권', '총거리'], ascending=[False, False]).reset_index(drop=True)
    
    medals = ["🥇", "🥈", "🥉"]
    
    html_content = "<div style='display: flex; justify-content: space-between; gap: 8px; text-align: center; margin-bottom: 20px;'>"
    
    for i in range(min(len(ticket_rank), 3)):
        row = ticket_rank.iloc[i]
        html_content += "<div style='flex: 1; padding: 10px 5px; border-radius: 10px; background-color: #f0f2f6; box-shadow: 1px 1px 3px rgba(0,0,0,0.1);'>"
        html_content += f"<div style='font-size: 1.5rem; margin-bottom: 2px;'>{medals[i]}</div>"
        html_content += f"<div style='font-size: 0.85rem; font-weight: bold; margin-bottom: 2px; color: #333;'>{row['이름']}</div>"
        html_content += f"<div style='font-size: 0.95rem; color: #ff4b4b; font-weight: bold;'>{row['총추첨권']}장</div>"
        html_content += "</div>"
        
    html_content += "</div>"
    st.markdown(html_content, unsafe_allow_html=True)
    
    # 2) 5만m 거리 랭킹
    st.markdown("##### 🏃 누적 거리 순위")
    dist_rank = ticket_df.sort_values(by='총거리', ascending=False).reset_index(drop=True)
    for i in range(min(len(dist_rank), 5)): 
        row = dist_rank.iloc[i]
        달성률 = min(float(row['총거리'] / TARGET_METERS), 1.0)
        
        st.write(f"**{i+1}위. {row['이름']}** ({row['총거리']:,.0f}m)")
        st.progress(달성률)

# ==========================================
# 탭 2: 내 기록실 (My Page)
# ==========================================
with tab2:
    st.subheader("🔍 내 기록 찾아보기")
    
    member_list = sorted(list(df['이름'].unique()))
    my_name = st.selectbox("본인의 이름을 선택하세요", ["선택해주세요"] + member_list)
    
    if my_name != "선택해주세요":
        my_data = df[df['이름'] == my_name]
        my_ticket = ticket_df[ticket_df['이름'] == my_name].iloc[0]
        
        st.success(f"환영합니다, **{my_name}**님! 💪")
        
        # 개인 KPI
        c1, c2 = st.columns(2)
        c1.metric("내 추첨권", f"🎟️ {my_ticket['총추첨권']} 장", f"기본 {my_ticket['기본추첨권']} + 보너스 {my_ticket['보너스추첨권']}")
        c2.metric("내 누적 거리", f"🏃 {my_ticket['총거리']:,.0f} m", f"인증 횟수: {my_ticket['참여횟수']}회")
        
        # 5만미터 달성 현황
        st.markdown("##### 🎯 50,000m 보너스(3장) 진행도")
        my_progress = min(float(my_ticket['총거리'] / TARGET_METERS), 1.0)
        my_remain = max(0, TARGET_METERS - my_ticket['총거리'])
        st.progress(my_progress)
        if my_remain > 0:
            st.caption(f"보너스까지 **{my_remain:,.0f}m** 남았습니다. 화이팅!")
        else:
            st.balloons()
            st.caption("🎉 50,000m 달성! 보너스 추첨권 3장이 지급되었습니다.")
            
        # 개인 훈련 내역 (표)
        st.markdown("##### 📝 최근 인증 내역")
        st.dataframe(
            my_data[['날짜', '운동종류', '총거리', '메모']].sort_values('날짜', ascending=False),
            use_container_width=True, hide_index=True
        )

        # 내 사진 갤러리 섹션
        st.markdown("##### 📸 내 인증 사진 모아보기")
        my_photos = my_data[my_data['사진링크'].astype(str).str.contains("http", na=False)].copy()
        
        my_photos = my_photos.sort_values(by='날짜', ascending=False)

        if my_photos.empty:
            st.caption("등록된 사진이 없습니다.")
        else:
            img_cols = st.columns(2)
            for idx, row in my_photos.iterrows():
                img_urls = extract_drive_image_urls(row['사진링크'])
                if img_urls:
                    date_str = row['날짜'].strftime('%m/%d %H:%M') if pd.notna(row['날짜']) else ""
                    with img_cols[list(my_photos.index).index(idx) % 2]:
                        st.image(img_urls[0], caption=f"{date_str} ({row['총거리']:,.0f}m)", use_container_width=True)
    else:
        st.info("👆 위에서 이름을 선택하면 개인 기록을 볼 수 있습니다.")

# ==========================================
# 탭 3: 인증 갤러리 (인스타그램 피드 스타일)
# ==========================================
with tab3:
    st.subheader("📸 훈련 갤러리")
    st.caption("부원들의 뜨거운 땀방울을 확인하세요!")
    
    photo_df = df[df['사진링크'].astype(str).str.contains("http", na=False)].copy()
    
    # 시간 단위까지 정확해진 날짜를 기준으로 완벽하게 최신순 정렬
    photo_df = photo_df.sort_values(by='날짜', ascending=False)
    
    if photo_df.empty:
        st.write("아직 사진이 없습니다.")
    else:
        for _, row in photo_df.head(10).iterrows():
            # 날짜와 시간이 보기 좋게 표기됨
            date_str = row['날짜'].strftime('%Y-%m-%d %H:%M') if pd.notna(row['날짜']) else ""
            st.markdown(f"**{row['이름']}** 님의 인증 🏃‍♂️ ({date_str})")
            
            if pd.notna(row['메모']) and row['메모'] != "":
                st.caption(f"💬 {row['메모']}")
                
            img_urls = extract_drive_image_urls(row['사진링크'])
            if img_urls:
                st.image(img_urls[0], use_container_width=True) 
            st.divider()
