import json,re,sys,time,unicodedata
from datetime import datetime,timedelta,timezone
from pathlib import Path
import requests
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data.json'; URL='https://t.me/s/slay_awards'; CATS=['SLAY King','SLAY Queen','Лучший CS-стример','Лучший Dota-стример','Лучший multigaming-стример','NEXT GEN','Лучший IRL-стример','Проект года на Twitch','Аудитория года','Пара года','Завоз года','Трек года','Косплеер года','Ютубер года','Лучший Minecraft-стример','Человек-мем года']
EM=re.compile('[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D\u20E3]')
def clean(s):return re.sub(r'\s+',' ',EM.sub('',unicodedata.normalize('NFC',s))).strip(' \t\r\n;,.')
def canon(c,v):
 if c in ('Проект года на Twitch','Завоз года'):
  s=clean(v).strip('«»“”"\'').replace('Bосхождение','Восхождение').replace('EgorikShkred','Егорик')
  if c=='Проект года на Twitch':
   normalized=re.sub(r'\s+',' ',s.casefold().replace('aфрике','африке').replace('&',' и ')).strip()
   if normalized=='выживание в африке' or re.fullmatch(r'африка\s+(?:leva2k\s+и\s+guacamolemolly|guacamolemolly\s+и\s+leva2k)',normalized):
    return 'Выживание в Африке'
  if c=='Завоз года' and s.casefold()=='мозгодел прицепился':return '5opka и мозгоеб'
  if s.casefold()=='восхождение на пик ленина':return 'Восхождение на пик Ленина'
  if s.casefold()=='егорик разрушает комнаты стримеров':return 'Егорик разрушает комнаты стримеров'
  if s.casefold() in ('медиа класико','betboom медиа класико'):return 'BetBoom Медиа Класико'
  return s
 if c=='Пара года':
  s=clean(v).replace('Диор Армани','Dior Armani');p=re.split(r'\s*(?:и|&)\s*',s)
  return ' & '.join(sorted([x.strip() for x in p],key=str.casefold)) if len(p)==2 else s
 if c=='Трек года':
  q=re.findall(r'[«“\"](.*?)[»”\"]',v); title=clean(q[-1] if q else v); before=v[:v.rfind(q[-1])] if q else '';after=v[v.rfind(q[-1])+len(q[-1])+1:] if q else '';m=re.search(r'от\s+(.+)$',after);artist=clean(m.group(1)) if m else clean(before.split('—')[0]).strip(' —');return f'{title} — {artist}' if artist else title
 return clean(v)
def extract(text):
    out = {}
    for chunk in text.split('•')[1:]:
        match = re.match(r'\s*(.+?)\s*—\s*(.*)$', chunk, re.S)
        if not match:
            continue
        category = match.group(1).strip()
        value = match.group(2).strip()
        if category not in CATS:
            continue
        value = re.sub(r'🤩\s*Проголосовать.*$', '', value, flags=re.S)
        value = re.sub(r'🤩\s*Купить билет.*$', '', value, flags=re.S)
        value = value.strip().rstrip(';').strip()
        if not value or re.search(r'\bне\s+(?:про)?голосовал(?:а|и)?\b', value, re.I):
            out[category] = ''
        else:
            out[category] = canon(category, value)
    return out


def author(text):
    triggers = r'(?:один из первых|показал[аи]?|продолжает|считает|считают|подключил(?:ся|ась)?|поделил(?:ся|ась)?|проголосовал(?:а|и)?|выбра(?:л|ла|ли)|распределил(?:а|и)?|отдал(?:а|и)?|назвал(?:а|и)?|не остал(?:ся|ась|ись)|определил(?:ся|ась)?|присоединил(?:ся|ась)?|сделал(?:а|и)?|продемонстрировал(?:а|и)?|не изменяет|решил(?:а|и)?|голосует|остал(?:ся|ась|ись)|поддержал(?:а|и)?|наблюдает|оставил(?:а|и)?|пообещал(?:а|и)?)'
    normalized = clean(text)
    match = re.match(r'^\s*(@?[\w][\w.-]*)\s+' + triggers + r'\b', normalized, re.I | re.UNICODE)
    return match.group(1).lstrip('@') if match else ''


def main():
    data = json.loads(DATA.read_text(encoding='utf-8'))
    scan_from = '2026-11-21'
    moscow = timezone(timedelta(hours=3))

    def ballot_date(ballot):
        published_at = str(ballot.get('publishedAt') or '')
        if published_at:
            try:
                return datetime.fromisoformat(published_at.replace('Z', '+00:00')).astimezone(moscow).date().isoformat()
            except ValueError:
                pass
        value = str(ballot.get('date', ''))
        if len(value) >= 10 and value[4] == '-':
            return value[:10]
        if len(value) >= 10 and value[2] == '.' and value[5] == '.':
            return value[6:10] + '-' + value[3:5] + '-' + value[:2]
        return value

    known_authors = {'9443': 'DanilaGorilla', '9448': 'Exile', '9474': 'DmitryLixxx'}
    existing = {
        str(ballot['id']): ballot
        for ballot in data.get('ballots', [])
        if '2026-11-15' <= ballot_date(ballot) < scan_from
    }
    url = URL
    seen = set()
    for _ in range(60):
        response = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        wraps = soup.select('.tgme_widget_message_wrap')
        ids = []
        reached_before_window = False
        for wrap in wraps:
            message = wrap.select_one('.tgme_widget_message')
            body = wrap.select_one('.tgme_widget_message_text')
            timestamp = wrap.select_one('time[datetime]')
            if not message or not body:
                continue
            post = message.get('data-post', '')
            message_id = post.rsplit('/', 1)[-1] if '/' in post else ''
            if not message_id.isdigit():
                continue
            ids.append(int(message_id))
            seen.add(message_id)
            published_at = timestamp.get('datetime', '') if timestamp else ''
            text = body.get_text(' ', strip=True)
            try:
                published_date = datetime.fromisoformat(published_at.replace('Z', '+00:00')).astimezone(moscow).date().isoformat()
            except (ValueError, TypeError):
                continue

            if published_date < scan_from:
                reached_before_window = True
                continue

            votes = extract(text)
            voter = author(text)
            if voter and set(votes) == set(CATS):
                existing[message_id] = {
                    'id': message_id,
                    'author': known_authors.get(message_id, voter),
                    'date': published_date,
                    'publishedAt': published_at,
                    'postUrl': 'https://t.me/slay_awards/' + message_id,
                    'votes': votes
                }

        if reached_before_window or not ids:
            break
        url = URL + '?before=' + str(min(ids))

    for ballot in existing.values():
        message_id = str(ballot.get('id', ''))
        if message_id in known_authors:
            ballot['author'] = known_authors[message_id]
        ballot['postUrl'] = 'https://t.me/slay_awards/' + message_id
        ballot['votes'] = {
            category: canon(category, value) if value else ''
            for category, value in ballot.get('votes', {}).items()
        }

    data['ballots'] = sorted(existing.values(), key=lambda ballot: int(ballot['id']))
    data['updatedAt'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Saved ' + str(len(data['ballots'])) + ' ballots; ' + str(len(seen)) + ' Telegram posts checked from ' + scan_from)


if __name__ == '__main__':
    main()
