import qrcode
from PIL import Image, ImageDraw, ImageFont

# GitHub 저장소 URL (브라우저에서 열리는 주소)
url = "https://github.com/nli830052-cmd/Clush"

# QR 코드 생성
qr = qrcode.QRCode(
    version=1,
    error_correction=qrcode.constants.ERROR_CORRECT_H,  # 오류 정정 최고 수준
    box_size=12,
    border=3,
)
qr.add_data(url)
qr.make(fit=True)

# 색상 커스터마이징 (검정 → 네이비, 흰색 배경)
img = qr.make_image(fill_color="#1F497D", back_color="white").convert("RGB")

# 하단에 라벨 텍스트 추가
label_height = 50
new_img = Image.new("RGB", (img.width, img.height + label_height), "white")
new_img.paste(img, (0, 0))

draw = ImageDraw.Draw(new_img)
label = "Clush AI Work Assistant | GitHub"
# 기본 폰트로 텍스트 중앙 배치
bbox = draw.textbbox((0, 0), label)
text_width = bbox[2] - bbox[0]
x = (new_img.width - text_width) // 2
y = img.height + 12
draw.text((x, y), label, fill="#1F497D")

# 저장
output_path = r"C:\Clush\github_qr.png"
new_img.save(output_path)
print(f"✅ QR 코드 생성 완료: {output_path}")
