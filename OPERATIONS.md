# K-INSIDER LAB 운영 문서 (인수인계용)

사람이 매일 손대지 않아도 돌아가도록 만든 시스템의 전체 지도입니다. 운영자가 바뀌어도 이 문서만 보면 이어받을 수 있게 유지합니다.

## 1. 무엇을 하는 사업인가
- 한국 네이버 쇼핑 검색 수요(K-뷰티 제품·성분·브랜드, K-푸드)를 매일 측정해 해외 바이어·유통사·브랜드팀에게 영어로 제공합니다.
- 관세청 국가별 수출 실적을 함께 보여줍니다.
- 수익화 순서: 무료 콘텐츠 → 이메일 명단 → 유료 데이터 구독 → B2B 리포트·데이터 판매

## 2. 소유 자산
| 자산 | 위치 |
|---|---|
| 도메인 | kinsider-lab.com (Cloudflare, 계정 werkorea.office@gmail.com) |
| 웹사이트 | GitHub Pages, 저장소 `werkorea-office/kinsider-lab` |
| 이메일 명단 | Kit (계정 werkorea.office@gmail.com, 구독 폼 ID 10207075) |
| 신청자 기록(회사명·역할) | Formspree `mjygjowd` |
| 인스타그램 | @kinsiderlab_official |
| 링크드인 | 회사 페이지 linkedin.com/company/kinsider-lab (현재 발행은 개인 프로필) |
| 데이터 | `data/history.csv`(일별 전 기록), `data/signals.json`(급상승 신호 원장, 수정 금지), `data/exports.json`, `data/assets.csv`(자산 지표) |

## 3. 자동 일정 (한국 시간)
| 시각 | 작업 | 파일 |
|---|---|---|
| 매일 06:30 | 네이버 수집 → 신호 판정 → 사이트 생성 → 캐러셀 6장 → (1일) 월간 PDF → (월) 주간 이메일 예약 → 커밋 | `.github/workflows/daily.yml` |
| 매주 1회 | 관세청 수출통계 갱신 (7일 경과 시) | `pipeline/exports.py` |
| 매일 23:00 | 인스타그램 캐러셀 + 링크드인 PDF 문서 발행 → 자산 지표 기록 | `.github/workflows/social.yml` |
| 매주 월 12:00 | 인스타그램 토큰 자동 연장 | `social.yml` |
| 월요일 23:00 | 주간 브리프 이메일 발송 (Kit 예약, 미국 동부 오전 9시) | `pipeline/newsletter.py` |
| 매일 06:30 (신호가 난 날만) | 급상승 즉시 알림 이메일 (Kit 태그 "Breakout alerts" 구독자, 하루 최대 1통) | `pipeline/alerts.py` |

## 4. 비밀값 (GitHub → Settings → Secrets → Actions)
| 이름 | 용도 | 만료 |
|---|---|---|
| NAVER_HUB_KEY_ID / NAVER_HUB_KEY | 네이버 데이터랩 (NAVER API HUB, 디시전에스 NCP 계정) | 없음 |
| DATA_GO_KR_KEY | 관세청 수출입실적 (공공데이터포털) | 활용기간 확인 |
| IG_ACCESS_TOKEN | 인스타그램 발행 | 60일, 매주 자동 연장 |
| GH_SECRETS_TOKEN | 인스타 토큰 자동 저장용 GitHub 토큰 | 생성 시 정한 기한 |
| LINKEDIN_ACCESS_TOKEN | 링크드인 발행 | **60일, 수동 재발급** (53일째 실패 알림 메일) |
| KIT_API_KEY | 이메일 발송·지표 | 없음 |

## 5. 사람이 해야 하는 일 (전부)
1. **링크드인 토큰 재발급 (60일마다):** GitHub 실패 알림 메일이 오면 LinkedIn 개발자 앱 K-INSIDER LAB Publisher → Auth → 토큰 생성 → `LINKEDIN_ACCESS_TOKEN` 교체
2. **실패 알림 메일 확인:** GitHub Actions가 실패하면 메일이 옵니다. 로그의 마지막 오류 줄을 보면 원인이 나옵니다.
3. **월 1회 자산 지표 확인:** `data/assets.csv`
4. **분기 1회 규제 정보 재검토:** `config/compliance.json`(수입 체크리스트·품목별 주의사항). 규제가 바뀌면 문구와 `reviewed` 날짜를 고칩니다. 출처 없는 내용은 넣지 않습니다.

## 6. 품질 원칙 (바꾸지 말 것)
- 순위는 지수 10 미만을 제외하고, 기준 키워드는 순위에 넣지 않습니다.
- 급상승 신호는 2주 연속 상승만 인정하고, 28일 재판정 금지 기간을 둡니다. 결과는 7·14·28일에 기록하며 **원장은 수정·삭제하지 않습니다.**
- 제품 효능·"사라/사지 마라" 판정을 쓰지 않습니다. 측정한 수요와 사실 설명만 씁니다(가짜 리뷰·과장 광고 위험 차단).
- 데이터가 오래됐거나 일부 실패하면 사이트는 마지막으로 검증된 값을 유지하고, 카드는 새 데이터일 때만 만듭니다.
- 제휴 링크나 협찬을 도입하면 인스타그램은 Paid partnership 라벨, 본문·뉴스레터는 첫 링크 위에 관계 공개를 넣습니다.

## 7. 키워드 추가·변경
`config/watchlist.json`에서 세그먼트별 `keywords`에 `{"kw": 한글 검색어, "en": 영문명, "type": 분류, "note": 한 줄 설명}`을 추가합니다. 한 요청에 5개까지 들어가며, 기준 키워드 1개 + 4개씩 자동으로 묶입니다.

## 8. 점검 명령 (GitHub Actions → Run workflow)
- `daily.yml`, newsletter=`status`: 구독자 수와 예약된 이메일 확인
- `daily.yml`, newsletter=`draft`: 주간 이메일을 Kit에 초안으로만 생성
- `social.yml`, task=`dryrun`: 오늘 캐러셀을 게시하지 않고 업로드까지만 시험
- `social.yml`, task=`check`: 인스타 토큰 자동 저장 권한 점검
