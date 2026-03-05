import streamlit as st
import requests
import pandas as pd
from bs4 import BeautifulSoup
import time
import urllib3
import re
from datetime import datetime, timedelta
from collections import Counter
from kiwipiepy import Kiwi

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --------------------------------------------------------------------------
# 1. 크롤링 함수 (차단 회피 헤더 적용)
# --------------------------------------------------------------------------
def get_news_links_by_date(keyword, target_date):
    links = []
    page = 1
    date_str = target_date.strftime("%Y.%m.%d")
    
    # [핵심] 네이버를 속이기 위한 강력한 헤더
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.naver.com/",
        "Connection": "keep-alive"
    }
    
    while True:
        start_idx = (page - 1) * 10 + 1
        url = f"https://search.naver.com/search.naver?where=news&query={keyword}&sm=tab_pge&sort=0&photo=0&field=0&pd=3&ds={date_str}&de={date_str}&start={start_idx}"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            # 차단 여부 디버깅용 (화면에 에러 출력)
            if "시스템에서 비정상적인 접근" in response.text:
                st.error(f"⚠️ 네이버가 서버 접근을 차단했습니다. (날짜: {date_str})")
                break
                
            soup = BeautifulSoup(response.text, 'html.parser')
            news_items = soup.select("div.news_area")
            
            if not news_items: 
                break
            
            found_new = False
            for item in news_items:
                title_tag = item.select_one("a.news_tit")
                if title_tag:
                    link = title_tag['href']
                    title = title_tag.get_text()
                    if "news.naver.com" in link:
                        links.append({'Date': target_date, 'Title': title, 'Link': link})
                        found_new = True
            
            if not found_new: break
            
            page += 1
            if page > 20: break 
            time.sleep(0.5) # 딜레이를 조금 더 길게 (0.1 -> 0.5)
            
        except Exception as e:
            st.warning(f"접속 오류: {e}")
            break
            
    return links

def get_news_content(url):
    # 본문 크롤링도 헤더 추가
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        content = soup.select_one("#dic_area")
        if not content: content = soup.select_one("#articeBody")
        return content.get_text(strip=True) if content else None
    except:
        return None

def analyze_simple(df):
    st.markdown("---")
    st.subheader("📊 키워드 분석")
    with st.spinner("분석 중..."):
        all_text = " ".join(df['Content'].astype(str).tolist())
        kiwi = Kiwi()
        stop_words = ['뉴스', '기자', '사진', '제공', '무단', '배포', '금지', '저작권', '오늘', '지난', '이번', '관련']
        tokens = kiwi.tokenize(all_text)
        nouns = [t.form for t in tokens if t.tag in ['NNG', 'NNP'] and len(t.form) > 1 and t.form not in stop_words]
        
        if nouns:
            count = Counter(nouns)
            top_20 = count.most_common(20)
            chart_data = pd.DataFrame(top_20, columns=['단어', '빈도수']).set_index('단어')
            st.bar_chart(chart_data)

# --------------------------------------------------------------------------
# 2. 메인 실행 로직
# --------------------------------------------------------------------------
st.set_page_config(page_title="뉴스 수집기 Web", page_icon="🌐", layout="wide")
st.title("🌐 네이버 뉴스 수집기 (Web)")

with st.sidebar:
    st.header("설정")
    keyword = st.text_input("검색 키워드", placeholder="예: 인공지능")
    today = datetime.now().date()
    start_date = st.date_input("시작", today - timedelta(days=3))
    end_date = st.date_input("종료", today)

if st.button("🚀 수집 시작"):
    if not keyword:
        st.warning("키워드를 입력하세요.")
    else:
        total_data = []
        delta = end_date - start_date
        date_list = [start_date + timedelta(days=i) for i in range(delta.days + 1)]
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, target_date in enumerate(date_list):
            status_text.text(f"📅 {target_date} 데이터 요청 중...")
            day_links = get_news_links_by_date(keyword, target_date)
            
            for item in day_links:
                content = get_news_content(item['Link'])
                if content:
                    total_data.append({
                        'Date': item['Date'], 'Title': item['Title'], 
                        'Link': item['Link'], 'Content': content
                    })
            progress_bar.progress((i + 1) / len(date_list))
            
        if total_data:
            df = pd.DataFrame(total_data)
            st.success(f"✅ 완료! 총 {len(df)}건 수집됨")
            
            csv = df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(
                label="📥 엑셀(CSV) 다운로드",
                data=csv,
                file_name=f"news_{keyword}.csv",
                mime="text/csv"
            )
            analyze_simple(df)
        else:
            st.error("수집된 데이터가 0건입니다. 네이버가 클라우드 서버의 접근을 차단했을 가능성이 높습니다.")
            st.info("💡 팁: '무제한 수집'은 개인 PC(로컬)에서 가장 잘 작동합니다.")