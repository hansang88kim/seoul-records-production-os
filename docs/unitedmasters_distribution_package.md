# Seoul Records · UnitedMasters 웹 등록

UnitedMasters 탭에서 곡별 원본, 정사각형 커버, 발매 정보, 업로드 체크리스트를 준비합니다. 웹에서 기존 초안을 이어서 편집할 수 있고, 권리와 최종 설정을 검토한 뒤 계정 소유자가 심사를 요청합니다.

## Seoul Records 발매 표기 기준

- 영문 표기는 UnitedMasters용 1:1 커버 이미지의 문구에 적용합니다. 앨범 제목은 확정한 공식 제목을 입력합니다.
- 트랙 제목은 확정한 원문 표기를 사용합니다. 한글 곡 제목과 한글 파일명의 개별 원본 WAV를 그대로 업로드합니다.
- 모든 트랙의 `Songwriter/Composer`에 `DJ One Table`을 입력합니다. 제출 전 전곡의 크레딧을 대조합니다.

### 1:1 커버 디자인

- 승인된 원본 사진의 인물, 배경, 구도와 색감을 유지하고 텍스트 레이어를 편집합니다.
- 왼쪽 상단에 `Seoul` / `City Pop` / `Wave. 73`처럼 시리즈명과 해당 권호를 3줄로 배치합니다. 따뜻한 금색의 빈티지 붓글씨를 사용하고 각 줄의 시작을 조금씩 들여씁니다. Vol.73은 권호 숫자에 채도가 낮은 세이지색을 사용했습니다. 별도 부제가 승인되면 작은 영문 부제를 씁니다. 사진 속 모니터 등 커버에 포함된 문구도 필요할 때 영문으로 편집합니다.
- 오른쪽 하단에 `Seoul Records`를 같은 계열의 붓글씨로 작게 배치합니다. 정사각형 미리보기에서 글자가 인물의 얼굴을 가리지 않고 작은 크기에서도 읽히는지 확인합니다.

## 제출 패키지 만들기

1. Video Renderer에서 확정한 플레이리스트를 고릅니다. 예전 반복 재생 플랜은 같은 원본의 첫 등장 순서를 사용합니다.
2. 배포에 승인된 1:1 JPG/PNG를 고르거나 승인된 가로 원본의 경로를 입력합니다. 커버 로고와 부제의 영문 표기를 확인합니다. 가로 원본은 전체 프레임을 비율 그대로 3000×3000 가운데에 맞추고 위아래에 흰 여백을 넣습니다. 출력 미리보기에서 사람, 화면 속 소품, 곡 목록과 글자가 전부 보이는지 확인합니다.
3. 트랙마다 확정한 원문 제목을 `tracklist.csv`에 입력하고 개별 원본 WAV를 연결합니다. 배포용 원본 FLAC도 지원합니다. 영상의 원본 트랙이 이미 WAV/FLAC라면 그 파일을 사용합니다. 예를 들어 파일 `09_질문 있어.wav`에 대응하는 곡 제목이 `질문 있어?`라면 그 제목을 입력합니다.
4. 아티스트 프로필, 확정한 앨범 제목, 웹에서 선택할 장르, `New Release` 또는 `Re-Release`, 희망 발매일을 입력합니다. `Record Label`은 모든 발매에서 공란으로 둡니다. UPC/EAN은 확인된 경우 기록합니다. 곡별 작사·작곡 크레딧은 `DJ One Table`로 준비하고, 피처링, 프로듀서, 외부 샘플·비트·녹음, Explicit, Radio Edit, 가사 유무와 기존 ISRC를 확인합니다.
5. **UnitedMasters 패키지 생성**을 선택합니다. `cover/cover_upload_ready.*`, `audio_distribution_master/`, `tracklist.csv`, `release_metadata.json`을 확인합니다. ZIP에는 체크리스트와 이 안내서도 포함됩니다.

원본 음원은 바이트 그대로 복사됩니다. 파일의 번호나 Windows에서 사용할 수 없는 문자를 정리한 파일명은 `tracklist.csv`의 `source_file` 열에서 확인합니다. 영상용 `final_audio_mix.wav`, 페이드, 곡 사이 무음, MP3 참고 음원은 영상 작업에 사용합니다.

2026년 11월 웹 등록 사례의 커버 입력란은 정사각형 JPG/PNG, 3000–6000px, 72–300dpi, 40MB 이하를 표시했습니다. 음원 입력란은 WAV/FLAC, 곡당 150MB 미만을 표시했습니다. UnitedMasters 공식 음원 도움말은 16/24-bit, 44.1/48/96/176.4/192kHz를 지원한다고 안내합니다. 해당 릴리스의 실제 입력란에 나온 규격을 확인합니다.

## 웹 등록 순서

| 단계 | 화면에서 할 일 | 저장 또는 확인 기준 |
|---|---|---|
| 로그인 및 초안 | `Music`에서 `Seoul Records` 프로필과 발매 제목을 확인합니다. 기존 초안을 열거나 새 앨범을 `Release Music`에서 시작합니다. | 편집할 초안이 맞습니다. |
| Release Details | `Add Release Title`에 확정한 앨범 제목을 입력하고 `Select Genre`, `Release Type`, 지역/계정에 따라 표시되는 UPC/EAN을 확인합니다. `Add Record Label`은 비워 둡니다. `Upload Cover Art`로 커버를 올립니다. | `Draft Auto-Saved`, `Replace Cover Art`, 실제 미리보기를 확인합니다. |
| Upload Audio | 확정한 순서대로 원래 파일명의 개별 WAV를 올립니다. 대량 작업은 작은 묶음으로 올리고 각 묶음의 처리가 끝나면 다음 묶음을 올립니다. | 진행 표시가 사라지고 모든 곡에 길이가 표시되면 `Source File`의 개수·순서·파일명을 대조하고 `Next`로 갑니다. |
| Track Details | `Source File`에 대응하는 원문 곡 제목과 `Songwriter/Composer` 값 `DJ One Table`을 입력합니다. 곡별 옵션은 화면에 표시된 항목명으로 선택합니다. Explicit 선택 뒤 나타나는 `Is Radio Edit`와 `Instrumental/No lyrics`를 따로 확인합니다. | 전곡의 제목·크레딧·필수 선택이 저장되었는지 확인한 뒤 `Next`로 이동합니다. |
| Split Pay 및 Mastering | 합의한 배분을 적용합니다. 별도 배분 지시가 없는 서울레코즈 자체 발매는 기본 `100% Seoul Records`를 확인합니다. 유료 마스터링은 구매 지시가 있을 때 선택합니다. | 수익 배분과 구매 항목이 지시와 맞습니다. |
| Distribution Settings | 승인된 발매일을 선택합니다. 가장 빠른 발매 요청이면 달력의 첫 선택 가능일을 저장하고 그 날짜를 기록합니다. | `Review and Submit`에 저장된 날짜가 보입니다. |
| Review and Submit | 확정한 앨범 제목, 원문 곡 제목, 1:1 커버의 영문 문구와 배치, 전곡 `DJ One Table` 크레딧, 아티스트, 장르, AI 표기, 발매일, 곡 수, 순서, 재생시간과 증빙을 검토합니다. 선택한 발매일, 사용 권리, 약관, 인위적 스트리밍 및 Wallet 비용 차감 안내에 대해 해당 발매의 계정 소유자 확인을 받고 웹에서 `Submit`을 누릅니다. | 성공 화면 또는 `Submitted` 상태에서 같은 릴리스와 날짜를 확인하고 기록합니다. |

### 커버 권리 및 AI 표기

| 확인된 내용 | 입력 |
|---|---|
| 자체 제작이며 제3자 콘텐츠가 없는 커버 | 최초 업로드 때 **`No – I own the artwork`**를 선택합니다. |
| 제3자 이미지·캐릭터·로고 등이 있는 커버 | **`Yes – I’ll upload a license`**를 선택하고 `Add License`에 실제 사용 허가를 첨부합니다. 필수 증빙이 누락되면 저장된 초안에서 이어갑니다. |
| 커버 제작에 생성형 AI 사용 | 권리 선택과 별도로 **`AI used in cover art → Yes`**를 선택합니다. 음원에 AI가 사용된 경우도 사실에 맞게 표기합니다. |

커버 문구는 발매 제목과 크레딧에 맞춥니다. UnitedMasters는 제3자 로고·워터마크가 있는 커버를 피하도록 안내합니다. 허가 자료의 보유 여부와 실제 심사 결과를 각각 확인합니다.

### 곡별 필드

| 필드 | 입력 |
|---|---|
| Add track title | `tracklist.csv`에 있는 해당 곡의 원문 제목 |
| Contains 3rd party audio | 곡별 외부 샘플·비트·녹음 사용 사실과 해당 시 허가 |
| Explicit Content, Is Radio Edit | 실제 내용과 검열 편집 여부 |
| Instrumental/No lyrics | 가사 있는 곡은 `No`, 가사 없는 인스트루멘털은 `Yes` |
| Songwriter/Composer | 전곡 `DJ One Table` |
| ISRC, 피처링, 프로듀서, 가사 | 확인된 곡별 값. 신규 곡에 발급된 ISRC가 없으면 비워 둡니다. |
| 가격, 미리듣기 | 별도 지시가 없으면 사이트 기본값 |

## 복구 및 결과 기록

- **커버 `Failed to fetch`**. 재전송 전에 기존 커버 미리보기부터 확인합니다. 미리보기가 없으면 같은 초안을 다시 열고 승인된 파일로 재시도합니다.
- **음원 `File Missing` 또는 곡 수 부족**. 처리가 진행 중이면 업로드 화면에서 기다립니다. 정체되면 저장된 초안을 다시 확인하고, 실패한 행이 남아 있으면 같은 행에 원본을 다시 연결할 수 있는지 먼저 봅니다. 실제로 빠진 파일만 재시도합니다. 실패한 빈 행의 정리에 확인이 필요한 경우 확인을 받아 처리합니다. 초안을 새로 만들어 복구할 경우 제출할 초안 하나를 구분하고, 제출 전에 곡 수·순서·길이와 중복 여부를 대조합니다.
- **필수 필드 또는 권리 증빙 오류**. 누락된 항목을 기록하고 자료가 준비되면 저장된 초안에서 해당 부분을 보완합니다.
- **완료 기록**. 실제로 확인된 `Draft`, `Submitted` 또는 심사 대기, 승인, `Live` 상태를 기록합니다. 제목, 선택한 발매일, 확인 시간과 링크를 작업 기록에 남깁니다. 실제 스트리밍 공개는 `Live` 또는 스트리밍 링크로 확인합니다.

19곡 등록 사례에서는 48kHz·16-bit·스테레오 WAV를 `01 → 02–07 → 08–13 → 14–19` 묶음으로 전송했습니다. 전체 가로 프레임을 포함한 3000×3000 JPG를 만들고, 19개 파일·표시 제목·재생시간·크레딧을 대조했습니다. Vol.73은 한글 파일명의 WAV 24개를 여섯 곡씩 올려 모든 전송이 끝난 것을 확인한 뒤 곡 정보를 입력했습니다. 최종 화면에서 한글 제목 24개, 재생시간 24개, `DJ One Table` 24개와 영문 커버를 대조했습니다. 묶음 크기는 작업 사례이며, 장르·권리 표기·크레딧·발매일은 새 발매마다 확인합니다.

## UnitedMasters 공식 안내

- [웹 릴리스 업로드와 제출](https://support.unitedmasters.com/hc/en-us/articles/40254654934419-How-do-I-upload-my-music-for-distribution)
- [커버 이미지와 제3자 콘텐츠 기준](https://support.unitedmasters.com/hc/en-us/articles/1500004669322-What-should-I-do-if-my-release-is-rejected-because-of-its-cover-art)
- [음원 파일 사양](https://support.unitedmasters.com/hc/en-us/articles/36330531666579-What-bit-sample-rate-files-should-I-submit-for-my-releases)
- [음원과 커버의 AI 표기](https://support.unitedmasters.com/hc/en-us/articles/56941966944147-AI-Tagging-on-Streaming-Services)
