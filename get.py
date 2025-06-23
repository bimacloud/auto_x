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
            # Ambil kode dan ubah ke /detail/
            code = href.split('/watch/')[-1].strip('/')
            detail_url = f'https://javfun.store/watch/{code}/'
            links.add(detail_url)

    return sorted(links)

# === Contoh Pemakaian ===
category_url = 'https://javfun.store/category/censored-3/'
detail_links = get_detail_links(category_url)

# Simpan ke file
with open('list_detail_links.txt', 'w') as f:
    for link in detail_links:
        f.write(link + '\n')

print(f"✅ Dapat {len(detail_links)} link detail. Disimpan ke list_detail_links.txt")
