#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
天津职业技术师范大学 - 全站通用爬虫
全站覆盖 | 通用提取 | 自动翻页 | 文件落地 | 强制日志
"""

import os
import re
import json
import time
import hashlib
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime


class GenericWebCrawler:
    """全站通用爬虫 - 支持多板块、自动翻页、文件落地存储"""

    # ============================================
    # 站点地图配置 - 所有要抓取的板块入口
    # ============================================
    SITE_MAP = {
        # 学校概况
        "学校概况": "http://www.tute.edu.cn/xxgk/xxjj.htm",
        "现任领导": "http://www.tute.edu.cn/xxgk/xrld.htm",
        "机构设置": "http://www.tute.edu.cn/xxgk/jgsz.htm",
        "历史沿革": "http://www.tute.edu.cn/xxgk/lsyg.htm",

        # 新闻资讯
        "校园新闻": "http://www.tute.edu.cn/index/xyxw.htm",
        "通知公告": "http://www.tute.edu.cn/index/tzgg.htm",
        "媒体报道": "http://www.tute.edu.cn/index/mtbd.htm",
        "视频新闻": "http://www.tute.edu.cn/index/spxw.htm",

        # 教育教学
        "本科教育": "http://www.tute.edu.cn/jyjx/bkjy.htm",
        "研究生教育": "http://www.tute.edu.cn/jyjx/yjsjy.htm",
        "职业教育": "http://www.tute.edu.cn/jyjx/zyjy.htm",
        "继续教育": "http://www.tute.edu.cn/jyjx/jxjy.htm",
        "留学生教育": "http://www.tute.edu.cn/jyjx/lxsjy.htm",

        # 招生就业
        "本科招生": "http://www.tute.edu.cn/zsjy/bkzs.htm",
        "研究生招生": "http://www.tute.edu.cn/zsjy/yjszs.htm",
        "就业信息": "http://www.tute.edu.cn/zsjy/jyxx.htm",

        # 学科科研
        "学科建设": "http://www.tute.edu.cn/xkky/xkjs.htm",
        "科学研究": "http://www.tute.edu.cn/xkky/kxyj.htm",
        "科研平台": "http://www.tute.edu.cn/xkky/kypt.htm",

        # 合作交流
        "国际交流": "http://www.tute.edu.cn/hzjl/gjjl.htm",
        "校企合作": "http://www.tute.edu.cn/hzjl/xqhz.htm",
        "校地合作": "http://www.tute.edu.cn/hzjl/xdhz.htm",
    }

    # ============================================
    # 通用提取器配置 - 匹配多个可能的正文标签
    # ============================================
    CONTENT_SELECTORS = [
        # 天职师大专用
        ".v_news_content",           # 最常见的内容容器
        "#vsb_content",              # 另一个常见容器
        ".v_news_content_div",       # 变体
        "#vsb_content_div",          # 变体

        # 通用选择器
        ".content-detail",           # 内容详情
        ".news-content",             # 新闻内容
        ".news_detail",              # 新闻详情
        ".v_news",                   # 简写
        ".content",                  # 通用内容
        ".main-content",             # 主内容区
        ".article-content",          # 文章内容
        ".detail-content",           # 详情内容
        ".text-content",             # 文本内容
        "article",                   # HTML5 article标签
        ".view",                     # 通用view
        "#content",                  # ID内容
        ".entry-content",            # 博客类
        ".post-content",             # 文章类
    ]

    # 列表页选择器 - 匹配文章链接
    LIST_SELECTORS = [
        ".news_list li a",           # 新闻列表
        ".list-txt li a",            # 文本列表
        ".list li a",                # 通用列表
        ".news-list li a",           # 新闻列表变体
        ".content-list li a",        # 内容列表
        ".listbox li a",             # 列表框
        ".left .listbox li a",       # 左侧列表
        "#list_content_table a",     # 表格列表
        ".newsBox li a",             # 新闻盒子
        ".listBox li a",             # 列表盒子
        "[class*='news'] li a",      # 包含news的类
        "[class*='list'] li a",      # 包含list的类
        "td a[href$='.htm']",        # 表格链接
        "td a[href$='.html']",       # HTML链接
    ]

    # 分页选择器
    PAGINATION_SELECTORS = [
        ".pages a",                  # 分页链接
        ".page a",                   # 页码
        ".pagination a",           # 标准分页
        ".next",                     # 下一页类
        ".nextpage",                 # 下一页
        ".page-next",                # 下一页变体
        ".p_next a",                 # 下页
    ]

    # ============================================
    # 特殊页面处理 - 领导信息页面需要单独解析
    # ============================================
    LEADER_PAGE_URLS = [
        "xrld.htm",                  # 现任领导
        "lrld.htm",                  # 历任领导
    ]

    def __init__(self, delay=1.5, max_pages_per_section=3, max_articles_per_page=10,
                 knowledge_base_dir="knowledge_base", temp_kb_dir="temp_kb"):
        """
        初始化爬虫

        Args:
            delay: 请求间隔(秒)
            max_pages_per_section: 每个板块最大抓取页数
            max_articles_per_page: 每页最大抓取文章数
            knowledge_base_dir: 知识库保存目录
            temp_kb_dir: 临时爬取目录（用于静默更新）
        """
        self.delay = delay
        self.max_pages_per_section = max_pages_per_section
        self.max_articles_per_page = max_articles_per_page
        self.knowledge_base_dir = knowledge_base_dir
        self.temp_kb_dir = temp_kb_dir

        # 创建会话
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
        })

        # 状态跟踪
        self.visited_urls = set()
        self.index_counter = 0
        self.stats = {
            'total_articles': 0,
            'success_count': 0,
            'error_count': 0,
            'by_section': {},
        }

        # 清理并创建临时目录
        self._ensure_temp_kb()

    def _ensure_temp_kb(self):
        """清理并创建临时爬取目录"""
        import shutil
        if os.path.exists(self.temp_kb_dir):
            shutil.rmtree(self.temp_kb_dir)
        os.makedirs(self.temp_kb_dir, exist_ok=True)
        print(f"[知识库] 创建临时目录: {self.temp_kb_dir}")

    def _swap_kb(self):
        """
        原子性替换：将临时目录替换为正式知识库
        使用备份-替换-清理的策略保证 AI 始终有数据可读
        """
        import shutil
        import time

        backup_dir = f"{self.knowledge_base_dir}_backup_{int(time.time())}"

        print(f"\n{'='*60}")
        print("执行知识库静默更新...")
        print(f"{'='*60}")

        try:
            # 1. 如果旧知识库存在，将其重命名为备份
            if os.path.exists(self.knowledge_base_dir):
                print(f"[1/3] 备份旧知识库 -> {backup_dir}")
                shutil.move(self.knowledge_base_dir, backup_dir)
            else:
                print("[1/3] 旧知识库不存在，跳过备份")

            # 2. 将临时目录重命名为正式知识库
            print(f"[2/3] 将临时目录替换为正式知识库")
            shutil.move(self.temp_kb_dir, self.knowledge_base_dir)

            # 3. 删除旧备份
            if os.path.exists(backup_dir):
                print(f"[3/3] 清理备份目录")
                shutil.rmtree(backup_dir)

            print(f"{'='*60}")
            print("[OK] 知识库更新完成！")
            print(f"{'='*60}")
            return True

        except Exception as e:
            print(f"[错误] 替换失败: {e}")
            # 如果失败，尝试恢复备份
            if os.path.exists(backup_dir) and not os.path.exists(self.knowledge_base_dir):
                print("[恢复] 尝试恢复备份...")
                shutil.move(backup_dir, self.knowledge_base_dir)
            return False

    def _sanitize_filename(self, filename):
        """清理文件名，移除非法字符"""
        # 移除Windows不允许的字符
        filename = re.sub(r'[\\/:*?"<>|]', '_', filename)
        # 移除多余空格
        filename = re.sub(r'\s+', '_', filename)
        # 限制长度
        if len(filename) > 100:
            filename = filename[:100]
        return filename.strip('_')

    def _generate_index(self):
        """生成索引编号"""
        self.index_counter += 1
        return f"[{self.index_counter:04d}]"

    def fetch(self, url, retries=3):
        """
        获取页面内容，带重试机制

        Returns:
            str: HTML内容，失败返回None
        """
        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=30)
                response.encoding = response.apparent_encoding or 'utf-8'

                if response.status_code == 200:
                    return response.text
                elif response.status_code == 404:
                    print(f"  [跳过] 页面不存在 (404): {url}")
                    return None
                else:
                    print(f"  [警告] HTTP {response.status_code}: {url}")

            except requests.exceptions.Timeout:
                print(f"  [超时] 尝试 {attempt + 1}/{retries}: {url}")
            except requests.exceptions.ConnectionError:
                print(f"  [连接错误] 尝试 {attempt + 1}/{retries}: {url}")
            except Exception as e:
                print(f"  [错误] {e}: {url}")

            if attempt < retries - 1:
                time.sleep(self.delay * (attempt + 1))

        return None

    def extract_generic_content(self, html, url):
        """
        通用内容提取器 - 尝试匹配多个可能的正文标签

        Args:
            html: 页面HTML
            url: 页面URL

        Returns:
            dict: {'title': str, 'content': str, 'url': str} 或 None
        """
        soup = BeautifulSoup(html, 'html.parser')

        # 移除干扰元素
        for elem in soup(['script', 'style', 'nav', 'header', 'footer', 'iframe', 'aside']):
            elem.decompose()

        # 提取标题
        title = ""
        title_selectors = ['h1', 'h2', '.title', '.news-title', '.article-title',
                          '[class*="title"]', '[class*="heading"]']
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                if len(title) > 5:  # 确保标题有效
                    break

        # 尝试多个内容选择器
        content_elem = None
        used_selector = None

        for selector in self.CONTENT_SELECTORS:
            elem = soup.select_one(selector)
            if elem:
                # 检查内容长度，过滤太短的
                text_length = len(elem.get_text(strip=True))
                if text_length > 50:  # 至少50个字符才算有效内容
                    content_elem = elem
                    used_selector = selector
                    break

        # 如果没找到，尝试从body提取
        if not content_elem:
            body = soup.find('body')
            if body:
                content_elem = body
                used_selector = "body"

        if not content_elem:
            return None

        # 提取纯文本
        text = content_elem.get_text(separator='\n', strip=True)

        # 清洗文本
        text = self.clean_text(text)

        # 调试信息
        if used_selector:
            print(f"    [提取器] 使用选择器: {used_selector} ({len(text)} 字符)")

        return {
            'title': title,
            'content': text,
            'url': url,
            'selector': used_selector,
        }

    def clean_text(self, text):
        """
        清洗文本内容
        """
        if not text:
            return ""

        # 移除多余空行
        text = re.sub(r'\n\s*\n+', '\n\n', text)

        # 移除多余空格
        text = re.sub(r'[ \t]+', ' ', text)

        # 移除常见噪声
        noise_patterns = [
            r'分享到[\s\S]*?(?=\n|$)',
            r'打印本文[\s\S]*?(?=\n|$)',
            r'关闭窗口[\s\S]*?(?=\n|$)',
            r'上一篇[\s\S]*?(?=\n|$)',
            r'下一篇[\s\S]*?(?=\n|$)',
            r'发布时间[：:]\s*\d{4}[\-\/年]\d{1,2}[\-\/月]\d{1,2}[日]?',
            r'阅读次数[：:]\s*\d+',
            r'【.*?】',  # 方括号内容
            r'\(\d{4}-\d{2}-\d{2}\)',  # 日期括号
        ]

        for pattern in noise_patterns:
            text = re.sub(pattern, '', text)

        # 清理首尾空白
        text = text.strip()

        return text

    def parse_list_page(self, html, base_url):
        """
        解析列表页，提取文章链接

        Returns:
            list: [{'title': str, 'url': str}, ...]
        """
        soup = BeautifulSoup(html, 'html.parser')
        articles = []

        for selector in self.LIST_SELECTORS:
            links = soup.select(selector)
            if links:
                print(f"    [列表选择器] {selector} -> {len(links)} 条")
                for link in links:
                    href = link.get('href', '')
                    title = link.get_text(strip=True)

                    # 过滤无效链接
                    if not href or not title:
                        continue
                    if href.startswith(('javascript:', '#', 'mailto:')):
                        continue

                    # 转换为完整URL
                    full_url = urljoin(base_url, href)

                    # 确保同域名
                    if 'tute.edu.cn' not in full_url:
                        continue

                    articles.append({
                        'title': title,
                        'url': full_url,
                    })

                if articles:
                    break

        # 去重
        seen = set()
        unique_articles = []
        for article in articles:
            if article['url'] not in seen:
                seen.add(article['url'])
                unique_articles.append(article)

        return unique_articles

    def get_next_page_url(self, html, base_url):
        """
        获取下一页链接

        Returns:
            str: 下一页URL或None
        """
        soup = BeautifulSoup(html, 'html.parser')

        # 1. 优先通过文本查找"下一页"
        next_keywords = ['下一页', '下页', 'Next', 'NEXT', 'next', '>', '>>']
        for keyword in next_keywords:
            # 完全匹配
            next_link = soup.find('a', string=keyword)
            if next_link:
                href = next_link.get('href', '')
                if href and not href.startswith('javascript:'):
                    return urljoin(base_url, href)

            # 包含匹配
            next_links = soup.find_all('a')
            for link in next_links:
                if keyword in link.get_text(strip=True) and len(link.get_text(strip=True)) < 10:
                    href = link.get('href', '')
                    if href and not href.startswith('javascript:'):
                        return urljoin(base_url, href)

        # 2. 尝试分页选择器
        for selector in self.PAGINATION_SELECTORS:
            pages = soup.select(selector)
            for page in pages:
                text = page.get_text(strip=True)
                classes = ' '.join(page.get('class', []))
                if any(k in text for k in next_keywords) or 'next' in classes:
                    href = page.get('href', '')
                    if href and not href.startswith('javascript:'):
                        return urljoin(base_url, href)

        return None

    def save_article(self, section_name, title, content, url):
        """
        保存文章到知识库

        Returns:
            bool: 是否成功
        """
        index = self._generate_index()

        # 处理空标题
        if not title or len(title.strip()) < 3:
            # 从URL生成标题
            title = f"article_{hashlib.md5(url.encode()).hexdigest()[:8]}"

        # 生成文件名
        safe_section = self._sanitize_filename(section_name)
        safe_title = self._sanitize_filename(title)
        filename = f"{safe_section}_{safe_title}.txt"
        filepath = os.path.join(self.temp_kb_dir, filename)

        # 处理重名
        counter = 1
        base_filepath = filepath
        while os.path.exists(filepath):
            name, ext = os.path.splitext(base_filepath)
            filepath = f"{name}_{counter}{ext}"
            counter += 1

        try:
            # 构建文件内容
            file_content = f"""标题: {title}
板块: {section_name}
来源: {url}
抓取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*60}

{content}
"""
            # 写入文件
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(file_content)

            # 强制日志输出
            print(f"  {index} 已存入: {os.path.basename(filepath)}")

            # 更新统计
            self.stats['success_count'] += 1
            if section_name not in self.stats['by_section']:
                self.stats['by_section'][section_name] = {'success': 0, 'error': 0}
            self.stats['by_section'][section_name]['success'] += 1

            return True

        except Exception as e:
            # 错误日志
            print(f"  {index} 保存失败: {os.path.basename(filepath)}")
            print(f"    [错误原因] {str(e)}")

            # 更新统计
            self.stats['error_count'] += 1
            if section_name not in self.stats['by_section']:
                self.stats['by_section'][section_name] = {'success': 0, 'error': 0}
            self.stats['by_section'][section_name]['error'] += 1

            return False

    def crawl_section(self, section_name, list_url):
        """
        爬取单个板块

        Args:
            section_name: 板块名称
            list_url: 列表页URL

        Returns:
            int: 成功抓取的文章数
        """
        print(f"\n{'='*60}")
        print(f"[板块] {section_name}")
        print(f"[入口] {list_url}")
        print(f"{'='*60}")

        current_url = list_url
        page_count = 0
        section_success = 0

        while current_url and page_count < self.max_pages_per_section:
            page_count += 1
            print(f"\n  [第 {page_count} 页] {current_url}")

            # 获取列表页
            html = self.fetch(current_url)
            if not html:
                print(f"  [错误] 无法获取页面: {current_url}")
                break

            # 解析文章列表
            articles = self.parse_list_page(html, current_url)
            print(f"  [发现] {len(articles)} 篇文章")

            if not articles:
                print("  [警告] 未找到文章链接，可能选择器不匹配")

            # 限制每页处理数
            articles = articles[:self.max_articles_per_page]

            # 处理每篇文章
            for article in articles:
                article_url = article['url']

                # 跳过已访问
                if article_url in self.visited_urls:
                    continue
                self.visited_urls.add(article_url)

                self.stats['total_articles'] += 1

                # 获取详情页
                detail_html = self.fetch(article_url)
                if not detail_html:
                    print(f"    [跳过] 无法获取详情页: {article_url}")
                    continue

                # 提取内容
                data = self.extract_generic_content(detail_html, article_url)
                if not data or not data.get('content'):
                    print(f"    [跳过] 无法提取内容: {article_url}")
                    continue

                # 使用列表页标题（通常更可靠）
                if article.get('title'):
                    data['title'] = article['title']

                # 保存到知识库
                success = self.save_article(
                    section_name=section_name,
                    title=data['title'],
                    content=data['content'],
                    url=article_url
                )

                if success:
                    section_success += 1

                # 礼貌延迟
                time.sleep(self.delay)

            # 获取下一页
            next_url = self.get_next_page_url(html, current_url)
            if next_url and next_url != current_url:
                current_url = next_url
            else:
                print(f"\n  [结束] 第 {page_count} 页后无更多页面")
                break

        print(f"\n  [板块完成] {section_name}: 成功 {section_success} 篇")
        return section_success

    def crawl_all(self):
        """
        爬取所有配置的板块

        Returns:
            dict: 统计信息
        """
        print("="*70)
        print("天津职业技术师范大学 - 全站通用爬虫")
        print("="*70)
        print(f"目标板块数: {len(self.SITE_MAP)}")
        print(f"每板块页数: {self.max_pages_per_section}")
        print(f"知识库目录: {self.knowledge_base_dir}")
        print("="*70)

        start_time = time.time()

        for section_name, url in self.SITE_MAP.items():
            self.crawl_section(section_name, url)
            # 板块间延迟
            time.sleep(self.delay * 2)

        # 输出统计
        elapsed = time.time() - start_time
        print("\n" + "="*70)
        print("爬取完成统计")
        print("="*70)
        print(f"总耗时: {elapsed:.1f} 秒")
        print(f"总文章数: {self.stats['total_articles']}")
        print(f"成功保存: {self.stats['success_count']}")
        print(f"保存失败: {self.stats['error_count']}")
        print("\n各板块详情:")
        for section, counts in self.stats['by_section'].items():
            print(f"  - {section}: 成功 {counts['success']}, 失败 {counts['error']}")

        # 保存统计到临时目录的JSON
        stats_file = os.path.join(self.temp_kb_dir, "_crawl_stats.json")
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'stats': self.stats,
                'config': {
                    'max_pages': self.max_pages_per_section,
                    'max_articles': self.max_articles_per_page,
                    'delay': self.delay,
                }
            }, f, ensure_ascii=False, indent=2)
        print(f"\n[统计] 已保存到: {stats_file}")

        # 执行静默更新 - 一键替换到正式知识库
        if self.stats['success_count'] > 0:
            self._swap_kb()
        else:
            print("\n[警告] 未成功抓取任何文章，跳过替换")

        return self.stats


def main():
    """主函数 - 全站爬取（使用静默更新机制）"""
    crawler = GenericWebCrawler(
        delay=1.5,                      # 请求间隔
        max_pages_per_section=3,        # 每板块抓3页
        max_articles_per_page=10,       # 每页最多10篇
        knowledge_base_dir="knowledge_base",
        temp_kb_dir="temp_kb"           # 临时爬取目录
    )

    # 执行全站爬取
    stats = crawler.crawl_all()

    return stats


if __name__ == '__main__':
    main()
