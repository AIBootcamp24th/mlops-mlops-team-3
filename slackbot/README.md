# Slackbot (3조 전용 알림)

`#1차_스터디_그룹_3조` 채널 전용 알림용 Slack Bot입니다.

## 환경변수

루트 `.env` 또는 `slackbot/.env`에 아래 키가 필요합니다.

- `SLACK_BOT_TOKEN`
- `SLACK_SIGNING_SECRET`
- `SLACK_APP_TOKEN`
- `SLACK_CHANNEL_ID`
- `SLACK_TARGET_CHANNEL_NAME`

## 실행

```bash
bun run dev
```

## 단건 알림

```bash
bun run notify "학습 파이프라인 완료"
```
