import re, json, requests
from datetime import datetime

def data_washing(response):
    cleaned_response = response.strip("```").strip("json\n")
    response_dict = json.loads(cleaned_response)
    num = response_dict['6_so']
    date = response_dict['ngay_xo']
    name = response_dict['ten_dai']
    name = extract_province(name)
    date = extract_date(date)
    return num, name, date

def extract_province(name):
    if name != None:
        name = name.lower()

        prefixes = [
            "xổ số", "kiến thiết", "tp", "tỉnh", "công ty",
            "đại hội nhân dân", "thành phố", "tnhh mtv", "bà rịa",
            "cty", "đoàn tncs", "phú quy", "cầu vàng", "xskt",
            "tnhh"
        ]
        for prefix in prefixes:
            name = name.replace(prefix, "")

        name = re.sub(r"[^\w\sÀ-ỹ]", "", name)
        name = re.sub(r"\s+", " ", name).strip()

        return " ".join([w.capitalize() for w in name.split()])


def extract_date(raw_text):
    match = re.search(r"(\d{1,2})[^0-9]?(\d{1,2})[^0-9]?(\d{4})", raw_text)
    if match:
        day, month, year = match.groups()
        return f"{int(day):02d}/{int(month):02d}/{year}"
    return None

    
def check_lottery_number(num, name, date):
    today = datetime.today()
    ticket_date = datetime.strptime(date, "%d/%m/%Y")
    if (today - ticket_date).days > 30:
        return "EXPIRED"
    
    if (today - ticket_date).days == 0 and (today < today.replace(hour = 17, minute = 15, second = 0, microsecond = 0)):
        return "NO_RESULTS_YET"
    
    if (today - ticket_date).days < 0:
        return "NO_RESULTS_YET"

    with open('lottery_apis.json', encoding='utf-8') as json_file:
        json_data = json.load(json_file)
        apis = json_data["lottery_apis"]
    
    if name not in apis:
        return None
    
    try:
        response = requests.get(apis[name])
        data = response.json()
        if not data['success']:
            return None
        
        for issue in data['t']['issueList']:
            if issue['turnNum'] == date:
                results = json.loads(issue['detail'])
                matched = []
                
                prize_names = [
                    "Đặc biệt", "Giải nhất", "Giải nhì", "Giải ba", 
                    "Giải tư", "Giải năm", "Giải sáu", "Giải bảy", "Giải tám"
                ]
                
                for i, result in enumerate(results):
                    numbers = result.split(',')
                    
                    for winning_num in numbers:
                        if num == winning_num:
                            matched.append((name, prize_names[i], winning_num))
                        
                        elif len(num) > len(winning_num) and num.endswith(winning_num):
                            matched.append((name, prize_names[i], winning_num))
                        
                        # Giải khuyến khích
                        if i == 0 and len(winning_num) == 6:
                            # Khuyến khích 1: sai 1 số đầu tiên
                            if num[1:] == winning_num[1:] and num[0] != winning_num[0]:
                                matched.append((name, "Khuyến khích 1", winning_num))
                            
                            # Khuyến khích 2: đúng số đầu, sai 1 số trong 5 số sau
                            if num[0] == winning_num[0]:
                                diff_count = 0
                                for j in range(1, 6):
                                    if num[j] != winning_num[j]:
                                        diff_count += 1
                                
                                if diff_count == 1:
                                    matched.append((name, "Khuyến khích 2", winning_num))
                
                return matched if matched else None
        
        return None
        
    except Exception as e:
        print(f"Lỗi khi gọi API: {e}")
        return None