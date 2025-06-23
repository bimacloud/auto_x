import requests
from bs4 import BeautifulSoup

def get_detail_links(category_url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(category_url, headers=headers)
    soup = BeautifulSoup(r.text, 'html.parser')

    links = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        if '/watch/' in href:
            code = href.split('/watch/')[-1].strip('/')
            detail_url = f'https://javfun.store/watch/{code}/'
            links.add(detail_url)

    return links

# 👇 BISA SATU LINK SAJA...
# category_url = 'https://javfun.store/category/censored-3/'

# 👇 ATAU MULTI LINK SEKALIGUS
category_url = [
    'https://javfun.store/category/censored-2/',
    'https://javfun.store/category/censored-4/',
    'https://javfun.store/category/censored-5/',
    'https://javfun.store/category/censored-6/',
]

all_links = set()

if isinstance(category_url, str):
    # Hanya satu kategori
    print(f"🔍 Mengambil dari: {category_url}")
    detail_links = get_detail_links(category_url)
    all_links.update(detail_links)
else:
    # Banyak kategori
    for url in category_url:
        print(f"🔍 Mengambil dari: {url}")
        detail_links = get_detail_links(url)
        all_links.update(detail_links)

# Simpan hasil
with open('list_detail_links.txt', 'w') as f:
    for link in sorted(all_links):
        f.write(link + '\n')

print(f"✅ Dapat total {len(all_links)} link detail. Disimpan ke list_detail_links.txt")
