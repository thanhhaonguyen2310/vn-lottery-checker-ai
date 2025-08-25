import torch
from PIL import Image
from transformers import AutoModel, AutoTokenizer
import torchvision.transforms as T
from torchvision.transforms.functional import InterpolationMode
from utils import data_washing, check_lottery_number

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

def build_transform(input_size):
    return T.Compose([
        T.Lambda(lambda img: img.convert('RGB') if img.mode != 'RGB' else img),
        T.Resize((input_size, input_size), interpolation=InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
    ])

def dynamic_preprocess(image, min_num=1, max_num=12, image_size=448, use_thumbnail=False):
    orig_width, orig_height = image.size
    aspect_ratio = orig_width / orig_height

    target_ratios = sorted(set(
        (i, j) for n in range(min_num, max_num + 1) for i in range(1, n + 1)
        for j in range(1, n + 1) if i * j <= max_num and i * j >= min_num
    ), key=lambda x: x[0] * x[1])

    def find_closest(aspect_ratio, target_ratios):
        return min(target_ratios, key=lambda r: abs(aspect_ratio - r[0] / r[1]))

    target_ratio = find_closest(aspect_ratio, target_ratios)
    target_width = image_size * target_ratio[0]
    target_height = image_size * target_ratio[1]
    blocks = target_ratio[0] * target_ratio[1]

    resized = image.resize((target_width, target_height))
    patches = []
    for i in range(blocks):
        box = (
            (i % (target_width // image_size)) * image_size,
            (i // (target_width // image_size)) * image_size,
            ((i % (target_width // image_size)) + 1) * image_size,
            ((i // (target_width // image_size)) + 1) * image_size
        )
        patches.append(resized.crop(box))

    if use_thumbnail and len(patches) != 1:
        patches.append(image.resize((image_size, image_size)))

    return patches

def load_image(image_file, input_size=448, max_num=6):
    image = Image.open(image_file).convert('RGB')
    patches = dynamic_preprocess(image, image_size=input_size, max_num=max_num, use_thumbnail=True)
    transform = build_transform(input_size)
    return torch.stack([transform(p) for p in patches])

# Chạy model local
#model = AutoModel.from_pretrained("C:/NLN2/Vintern-1B-v3_5", trust_remote_code=True)
#tokenizer = AutoTokenizer.from_pretrained("C:/NLN2/Vintern-1B-v3_5", trust_remote_code=True)

# Chạy online
model = AutoModel.from_pretrained("5CD-AI/Vintern-1B-v3_5", trust_remote_code=True)
tokenizer = AutoTokenizer.from_pretrained("5CD-AI/Vintern-1B-v3_5", trust_remote_code=True)

def process_lottery_image(image_path):
    question = '''<image>\nHãy phân tích ảnh tờ vé số và trả về duy nhất một đối tượng JSON theo cấu trúc sau:
        {
        "6_so": "xxxxxx",   // một chuỗi gồm 6 chữ số liên tiếp xuất hiện trên tờ vé số, in lớn nhất, thường xuất hiện nhiều lần lần trên vé, là dãy số dự thưởng chính
        "ten_dai": "Tên tỉnh/thành phố",  // ví dụ: "Vũng Tàu", "Đà Nẵng", "TP. Hồ Chí Minh"
        "ngay_xo": "dd/mm/yyyy"  // ngày mở thưởng in trên vé, ở định dạng dd/mm/yyyy
        }

        Quy tắc nhận diện:
        - Bỏ qua các con số liên quan đến mệnh giá tiền (ví dụ: 10.000đ, 10000), số seri nhỏ, số điện thoại, hoặc năm.
        - "6_so" phải đúng 6 chữ số liên tiếp, là dãy số chính của vé số, hay xuất hiện nhiều lần trên tờ vé số.
        - "ten_dai" lấy từ logo hoặc dòng chữ "XỔ SỐ KIẾN THIẾT …".
        - "ngay_xo" là ngày mở thưởng in rõ ràng trên vé.
        - Chỉ trả về JSON hợp lệ, không kèm thêm giải thích.'''
    pixel_values = load_image(image_path)
    generation_config = dict(max_new_tokens=512, do_sample=False, num_beams=3, repetition_penalty=3.5)

    response = model.chat(tokenizer, pixel_values, question, generation_config)
    del pixel_values # Xóa để trống tí ram

    num, name, date = data_washing(response)

    if num == None or name == None or date == None:
        return {
            'ticket_numbers': [num],
            'lottery_name': name,
            'lottery_date': date,
            'results': [],
            'total_prizes': -2,  # -2 = vé không nhận diện được
            'expired': True
        }

    matched = check_lottery_number(num, name, date)
    if matched == "EXPIRED":
        return {
            'ticket_numbers': [num],
            'lottery_name': name,
            'lottery_date': date,
            'results': [],
            'total_prizes': -1,  # -1 = vé quá hạn (30 days)
            'expired': True
        }

    if matched == "NO_RESULTS_YET":
        return {
            'ticket_numbers': [num],
            'lottery_name': name,
            'lottery_date': date,
            'results': [],
            'total_prizes': -3,  # -3 = vé chưa có kết quả xổ, mặc định trước 17h15 vì api từ 16h15 có kết quả
            'expired': True
        }

    return {
        'ticket_numbers': [num],
        'lottery_name': name,
        'lottery_date': date,
        'results': matched if matched else [],
        'total_prizes': len(matched) if matched else 0,
        'expired': False
    }