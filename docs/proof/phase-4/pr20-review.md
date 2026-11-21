# Review PR #20

Đã ghép main có phần tương phản cao và hồ sơ TV4/TV5. Giữ handle GitHub trong TEAM.md theo main, tránh lấy tên branch làm handle.

Sửa lỗi tương thích v1.3 ở gather/scenario/day. Các nhánh từng so version đúng bằng 1.2 nay dùng is_v12 để giữ schema cá thể khi nâng lên 1.3. Regression kiểm spoilage theo version và cấp I11 sau fixture I10 khi sang Ngày 2 ở v1.3.

Đánh dấu release notes là bản nháp, các lệnh benchmark/soak là dự kiến chờ tích hợp. Chưa công bố Release hay gắn tag.

Kiểm chứng
- Suite tích hợp 124/124 đạt. [Log](pr20-review.log)
- Bộ contract sau khi thêm test ID xuyên ngày đạt 12/12. [Log](pr20-contract-review.log)

Manifest hiện còn 1.1, các bài kiểm v1.3 dùng tuning/contract fixture. Nghiệm thu bản phát hành cần cấu hình v1.3 thật, bench/soak và kết quả QA trên commit phát hành.
