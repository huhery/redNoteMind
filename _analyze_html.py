import re

with open('./data/debug/card_sample.html', encoding='utf-8') as f:
    html = f.read()

# 找所有 href
hrefs = re.findall(r'href=["\']([^"\']+)["\']', html)
print('=== 所有 href ===')
for h in hrefs[:20]:
    print(h)

# 找所有 class，筛选疑似点赞/交互相关
all_classes = re.findall(r'class=["\']([^"\']+)["\']', html)
keywords = ['like', 'count', 'interact', 'footer', 'engage', 'info', 'stat', 'num', 'icon']
print('\n=== 疑似点赞/数量相关 class ===')
seen = set()
for c in all_classes:
    for part in c.split():
        low = part.lower()
        if any(k in low for k in keywords) and part not in seen:
            seen.add(part)
            print(part)

# 找 data-note-id 确认笔记真实 id 格式
note_ids = re.findall(r'data-note-id=["\']([^"\']+)["\']', html)
print('\n=== data-note-id ===')
for n in note_ids[:5]:
    print(n)
