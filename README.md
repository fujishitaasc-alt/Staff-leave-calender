# やすみの予定 — 職員専用 休暇予定共有サイト

Django 5.2 LTS 製。個人ログイン後、全員の休暇を閲覧し、本人の予定を登録・変更・取消します。登録は即時共有、承認はありません。管理者は職員・全員の予定・職種別注意基準を管理できます。スマホでは「日付順リスト」を利用できます。

## まずデモを試す（本番と分離）

Python 3.12 以上を推奨。リポジトリ直下で実行します。

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.lock
export DEMO=1 DEBUG=1
python manage.py migrate
python manage.py init_leave
python manage.py seed_demo
python manage.py runserver 127.0.0.1:8000
```

通常のブラウザから開発サーバーを開きます（クラウド環境では公開設定が別途必要）。`seed_demo` は架空の理学療法士10名・リハビリ助手3名を作り、**その場で生成した初回パスワードだけを端末に表示**します。`demo01` は管理者です。固定パスワードはありません。再実行で既存パスワードを変更しません。忘れた場合は `python manage.py changepassword demo01`。表示されたパスワードを Git や共有ログへ保存しないでください。

デモは `demo.sqlite3` を使用し、画面にデモと明示。本番設定では `seed_demo` は拒否されます。`DATABASE_URL` が設定済みだとそちらが優先されるため、デモ実行前に本番用 `DATABASE_URL` が未設定であることを確認してください。実名・本番情報をデモに入力しないでください。

## 本番運用の構成・手順

詳細は [運用手順](docs/operations.md)。推奨は **単一の Linux サーバー + Docker Compose + PostgreSQL + Caddy の HTTPS** です。DB・認証をアプリ側にまとめ、外部の認証サービス契約を不要にしています。ブラウザの保存領域ではなく、全端末が同一サーバーのデータベースを利用します。リポジトリの初期人数は固定ではありません。

1. 常時稼働サーバーとドメインを用意し、DNS を設定する。
2. `.env.example` を `.env` にコピーし、秘密鍵・DBパスワード・実際のドメインを設定する。
3. Docker を起動して、以下を実行する。

```sh
docker compose build
docker compose up -d db
docker compose run --rm app python manage.py migrate
docker compose run --rm app python manage.py init_leave
docker compose run --rm app python manage.py createsuperuser
# 対話入力で username、メール（省略可）、パスワードを設定します。
docker compose up -d
```

最初の管理者の職員名は管理画面で設定してください。`createsuperuser` は職種初期値が理学療法士です。該当しなければ変更します。

管理画面の「職員」から職員を追加し、氏名・職種・個別のユーザー名・初回パスワードを設定。管理者が個別に安全な方法で伝え、本人は初回ログイン後「パスワード変更」を実行します。一般公開の新規登録やメール送信はありません。一般職員には「有効」だけを付け、スタッフ権限・スーパーユーザー権限・グループ・個別権限を付与しないでください。管理者の追加は「有効」「スタッフ権限」「スーパーユーザー権限」を付けます。

退職・停止時は「有効」を外します。既存セッションも次のリクエストで拒否され、休暇記録は残ります。職員削除は管理画面で禁止、休暇からの外部キーも保護します。職種を変更すると過去の予定にも現在の職種を表示します。

## 時刻・人数・権限

- 日本時間、勤務時間 8:30–12:30 / 14:00–18:00。全日は480分。分単位の時間休暇は昼休憩を除き、昼休憩だけの登録は拒否。
- 区間の終端は含めず、12:00終了と12:00開始は重複なし。同一人物の実勤務時間内の重複をサーバーで拒否。同一人物の人数は集合で数える。
- 職種ごとの同時休暇人数を時間帯別表示。基準は初期未設定。「職種別注意基準」で1名以上を指定すると以上の時間帯に注意表示。注意は登録を禁止しない。空欄で未設定に戻せる。
- 公休・シフト・出勤人数・取得単位・残日数は扱わない。詳しい理由を入力する欄はない。
- `LeaveType` を独立させ、将来の特別休暇を追加可能。不要な種別は「利用可能」を外す（過去分は残る）。
- 未認証はカレンダー、一覧、変更、取消、管理画面を取得不可。本人判定はサーバーのログイン情報で行い、投稿された職員IDや権限を信用しない。CSRF保護・パスワードハッシュはDjango標準機構。
- PostgreSQL は職員行をロックして重複登録を直列化。SQLite 競合時は保存失敗を表示して再試行を促す。保存完了はDB保存成功後のみ表示。

## テスト

```sh
DEMO=1 python manage.py test
DEMO=1 python manage.py check
DEMO=1 python manage.py makemigrations --check --dry-run
```

本番接続を使わず、専用の一時テストDBで実行します。ログイン、停止職員、権限、重複、昼休憩、職種別人数、管理操作を検証します。確認済み・未確認の区別は [検証記録](docs/verification.md) を参照。

## ファイル

- `leave/models.py`：職員・休暇・注意基準・時間検証
- `leave/services.py`：同時休暇人数の計算
- `leave/views.py`：認証済み職員の閲覧・保存・取消
- `leave/admin.py`：管理者用操作
- `templates/`, `static/`：日本語・レスポンシブ画面
- `.env.example`：秘密情報を含まない設定例
- `compose.yaml`, `Dockerfile`, `Caddyfile`：本番構成例

Django / PostgreSQL / Caddy はオープンソースで利用料不要。常時稼働サーバー、ドメイン更新、外部バックアップ保管、管理型DBを選ぶ場合の利用量などに費用が発生します。無償枠の停止・永続ディスク制限に注意してください。
