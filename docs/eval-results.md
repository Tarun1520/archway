# Research evaluation results

Mode: live. Each part is 0 to 10 (see backend/evaluation/scoring.py).

| Case | Score | Coverage | Precision | Efficiency | Speed | Reliability | Calls | Minutes | Missed |
|---|---|---|---|---|---|---|---|---|---|
| voice-bot | **8.0** | 10.0 | 9.1 | 4.0 | 6.8 | 10.0 | 76 | 7.2 | none |
| pdf-study-helper | **8.2** | 6.0 | 9.1 | 6.0 | 9.7 | 10.0 | 64 | 4.3 | local embeddings, local language model runtime |
| word-designer | **8.3** | 5.0 | 10.0 | 6.5 | 9.9 | 10.0 | 61 | 4.1 | document conversion or preview, desktop UI toolkit |
| reminder-caller | **9.0** | 8.0 | 10.0 | 7.5 | 9.5 | 10.0 | 55 | 4.5 | push notifications |
| meeting-notes-bot | **8.8** | 10.0 | 8.9 | 6.0 | 9.0 | 10.0 | 64 | 5.0 | none |
| food-photo-nutrition | **8.8** | 7.5 | 7.5 | 9.0 | 10.0 | 10.0 | 46 | 3.2 | camera or image capture |

**Average: 8.5**

## Held-out ideas (no prompt was tuned on these), 2026-10-16

Mode: live. Each part is 0 to 10 (see backend/evaluation/scoring.py).

| Case | Score | Coverage | Precision | Efficiency | Speed | Reliability | Calls | Minutes | Missed |
|---|---|---|---|---|---|---|---|---|---|
| release-notes-cli | **8.6** | 10.0 | 9.5 | 4.2 | 9.5 | 10.0 | 75 | 4.5 | none |
| sensor-dashboard | **10.0** | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 36 | 2.6 | none |
| craft-shop | **8.3** | 6.7 | 9.3 | 6.0 | 9.5 | 10.0 | 64 | 4.5 | transactional email |
| group-trivia-game | **8.3** | 6.7 | 9.0 | 7.7 | 8.0 | 10.0 | 54 | 6.0 | browser UI or rendering |

**Average: 8.8**


## Held-out ideas after the core-processing and reviewer fixes, 2026-10-16

Mode: live. Each part is 0 to 10 (see backend/evaluation/scoring.py).

| Case | Score | Coverage | Precision | Efficiency | Speed | Reliability | Calls | Minutes | Missed |
|---|---|---|---|---|---|---|---|---|---|
| release-notes-cli | **10.0** | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 35 | 2.5 | none |
| sensor-dashboard | **8.9** | 10.0 | 9.1 | 5.8 | 9.7 | 10.0 | 65 | 4.3 | none |
| craft-shop | **8.2** | 6.7 | 8.3 | 7.8 | 8.0 | 10.0 | 53 | 6.0 | transactional email |
| group-trivia-game | **8.6** | 10.0 | 8.9 | 5.3 | 9.0 | 10.0 | 68 | 5.0 | none |

**Average: 8.9**

