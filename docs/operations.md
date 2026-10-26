# 運用・引き継ぎ

## 初期設定

Python 3.12 / Docker Compose v2 を想定。共通DBとHTTPSを備えたサーバーを1台運用します。初期設定を担当する人以外にSSHやDB接続を公開しないでください。

`.env.example` を `.env` にコピーし、ファイル権限を `chmod 600 .env` にします。`SECRET_KEY` と `POSTGRES_PASSWORD` はパスワード管理ツール等でそれぞれ異なる長いランダム英数字に生成して設定してください。コード・GitHub・チャットへ記載しないでください。`.env` は自動的にGit除外されています。

- `SITE_DOMAIN` / `ALLOWED_HOSTS`：実ドメイン（例 `leave.your-clinic.jp`）
- `CSRF_TRUSTED_ORIGINS`：`https://実ドメイン`
- `DEMO=0`, `DEBUG=0`：本番は固定。Compose も強制します。
- `SECRET_KEY`：全アプリインスタンス共通、バックアップも安全に保管。
- `POSTGRES_PASSWORD`：Compose用。URIに入るのでランダム英数字を推奨。

DNSのAレコードをサーバーへ向け、80/443番を開けます。Compose のDB・アプリ用ポートは外部に公開しません。Caddyが証明書を自動取得します。AAAAレコードを設定する場合はIPv6経由も接続できる必要があります。TLSのプロキシヘッダーを信頼する設定のため、**アプリ8000番を直接インターネットに公開せず、信頼するリバースプロキシ経由だけにしてください**。

READMEの構築コマンド後、HTTPSでログインし、管理画面で自分の職員名・職種を設定。13人分は本番の実際の職員として管理者が個別に追加してください。開発用デモ作成コマンドは使いません。運用開始時は注意基準を空欄のままにし、職場で決めてから設定できます。

## DB構築と更新

`migrate` はスキーマを作成・更新し、`init_leave` は通常休暇と未設定の職種別基準を作ります。再実行しても既存の基準を上書きしません。更新時はバックアップ後に以下を実施：

```sh
docker compose build
docker compose run --rm app python manage.py migrate
docker compose run --rm app python manage.py check --deploy
docker compose up -d
```

本番はPostgreSQL推奨。SQLiteで運用する場合は同じ単一サーバーの永続ファイルを全プロセスで共有し、ネットワークドライブに置かないでください。DBファイルが一時ディスクだと消失します。`DATABASE_URL=sqlite:////data/production.sqlite3` 等の永続絶対パスとアクセス権が必要です。ブラウザごとにDBを作る構成ではありません。

## 日常操作

- 管理者：職員作成・変更、利用停止、パスワード再設定、全員の休暇変更・取消、注意基準・休暇種別の編集。
- 一般職員：全員の予定閲覧、自分の休暇のみ登録・変更・取消、本人のパスワード変更。
- 共有や相談は職場で実施。チャット・承認・通知はありません。
- 利用停止しても履歴は残るため、退職者を再利用せず新しい人に新規アカウントを発行。
- 予定取消はDBから削除されます。取消履歴や変更履歴の完全な監査証跡は初期版の対象外です（管理画面の操作ログはDjango標準）。
- パスワードを忘れたら管理者が管理画面で再設定。メールによる自動リセットはありません。

## バックアップ

毎日と更新前に取得。バックアップにも職員情報が含まれるため、アクセス制限し、暗号化された別サーバー等へ保管します。

```sh
mkdir -p backups
chmod 700 backups
docker compose exec -T db pg_dump -U leave -d leave -Fc > backups/leave.dump
chmod 600 backups/leave.dump
```

`backups/` はGit除外済み。世代管理し、保管期間を職場で決めてください。同じファイルを上書きする例のため、実運用では日時別に分けます。復元は隔離した検証用DBで先に確認してください。本番DBの上書きは破壊的操作です。

```sh
# 空の復元先DBを作成済みの検証環境でのみ実行
# 検証環境の接続先であることを確認する
docker compose exec -T db pg_restore -U leave -d leave --no-owner < backups/leave.dump
```

`.env`、Caddy証明書ボリュームも安全にバックアップ。`docker compose down -v` はDBも消すため通常運用で実行しないこと。

## 公開前チェック・制限

HTTPS・実ドメイン・実データ・2台の端末でログインし、登録後に他方を再読み込みして共有を確認してください。画面はリロード時に最新DBを読む方式で、自動リアルタイム配信は行いません。失敗時は完了メッセージを出しません。

本番前に `check --deploy` を実行し、ログイン試行回数制限をリバースプロキシやホスティングのWAFで設定してください。初期版は多要素認証とアカウントロックを搭載していません。サーバーOS・依存関係を定期更新し、ログにはパスワードやPOST本文を収集しないでください。Djangoのセッションを定期削除するには `python manage.py clearsessions` をスケジュール登録します。

外部サービスのAPI鍵は不要です。実サーバー、DNS、証明書発行、バックアップ先、複数スマホでの接続はこの開発環境では未検証です。

`check --deploy` の HSTS サブドメイン適用とpreloadの警告は、使用するドメイン全体のHTTPS方針を確認してから対応します。関係するサブドメインがHTTPを必要とする場合、無条件に有効化しないでください。開発環境での結果は `docs/verification.md` に記録しています。
