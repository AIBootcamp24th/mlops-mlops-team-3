import path from "node:path";
import { App } from "@slack/bolt";
import dotenv from "dotenv";

dotenv.config();
dotenv.config({
  path: path.resolve(process.cwd(), "../.env"),
  override: false,
});

const REQUIRED_ENV_KEYS = [
  "SLACK_BOT_TOKEN",
  "SLACK_SIGNING_SECRET",
  "SLACK_APP_TOKEN",
  "SLACK_CHANNEL_ID",
] as const;

for (const key of REQUIRED_ENV_KEYS) {
  if (!process.env[key]) {
    throw new Error(`${key} 가 설정되지 않았습니다.`);
  }
}

const targetChannelId = process.env.SLACK_CHANNEL_ID as string;

const app = new App({
  token: process.env.SLACK_BOT_TOKEN,
  signingSecret: process.env.SLACK_SIGNING_SECRET,
  socketMode: true,
  appToken: process.env.SLACK_APP_TOKEN,
});

async function sendToTargetChannel(text: string) {
  await app.client.chat.postMessage({
    channel: targetChannelId,
    text,
  });
}

app.command("/mlops-alert", async ({ command, ack, respond }) => {
  await ack();

  if (command.channel_id !== targetChannelId) {
    await respond({
      response_type: "ephemeral",
      text: "이 명령어는 #1차_스터디_그룹_3조 채널에서만 사용할 수 있습니다.",
    });
    return;
  }

  const message = command.text?.trim() || "MLOps 파이프라인 알림";
  await sendToTargetChannel(`:satellite: ${message}`);
  await respond({
    response_type: "ephemeral",
    text: "알림을 전송했습니다.",
  });
});

async function bootstrap() {
  const [mode, ...rest] = process.argv.slice(2);

  if (mode === "notify") {
    const text = rest.join(" ").trim() || "MLOps 파이프라인 알림";
    await sendToTargetChannel(`:satellite: ${text}`);
    console.log("알림 전송 완료");
    return;
  }

  await app.start();
  console.log("Slack bot 실행 중 (/mlops-alert)");
}

bootstrap().catch((error) => {
  console.error(error);
  process.exit(1);
});
