# Myportfolio

## 採用担当者向けサマリー

このリポジトリは、業務で使うPC構成の作成を支援するWebアプリのポートフォリオです。
単なる画面実装だけでなく、データ収集（スクレイピング）、API設計、運用時の障害切り分けまでを一貫して扱っています。

### このポートフォリオで伝えたいこと

- 現場課題を踏まえた機能設計: 構成自動生成と手動置換を両立し、実運用での使いやすさを重視。
- 継続運用を意識した実装: データ整合性チェック、タイムアウト付きマイグレーション、ロック診断ツールを整備。
- 学習・適応力: Django REST Framework、React (Vite)、PostgreSQL、スクレイピング運用を横断して改善を継続。

### 想定利用シーン

- 予算や用途に応じたPC構成を短時間で作成したい。
- 在庫やパーツ情報の更新を継続し、提案品質を維持したい。
- 障害発生時に、原因を可視化して安全に復旧したい。

### 担当範囲（個人開発）

- 要件整理、API/データモデル設計、バックエンド実装、フロントエンド実装。
- スクレイピング処理、整合性検証スクリプト、運用補助スクリプトの作成。
- ローカル開発環境の起動導線整備（Windows向け起動スクリプト、タスク整備）。

### AI活用について

制作時には生成AIを活用し、実装案の比較、設計観点の洗い出し、検証手順の整理を行いながら開発を進めました。
最終的な要件判断、設計選定、実装内容の確認と修正は自身で実施し、動作検証と運用観点の確認を通じて品質を担保しています。

## 応募書類（公開版）

メール添付機能が利用できない場合に備え、応募書類をこのリポジトリ内に掲載しています。
以下の書類は公開版として個人情報を必要最小限にマスクした版を配置しています。

- 履歴書（PDF）: [履歴書.pdf](履歴書.pdf)
- 職務経歴書（PDF）: [職務経歴書.pdf](職務経歴書.pdf)
- ポートフォリオ（GitHub）: [Myportfolio](https://github.com/yuuichikaneko/Myportfolio)

## レビュアー向けガイド（公開共有）

このリポジトリはURLによるポートフォリオレビュー用として公開しています。

- 対象範囲: Django + React (Vite) を使った構成ビルダー（データスクレイピング・運用診断機能含む）
- 対象者: リポジトリURLをお持ちの方

### クイックレビュー手順

1. まず以下を順に確認:
	- Quick Start
	- PostgreSQL migration preparation (Django)
	- PostgreSQL freeze mitigation and diagnostics
2. バックエンドとフロントエンドを起動:

```bash
cd django
python manage.py runserver 8001

cd ../frontend
npm install
npm run dev
```

3. 動作確認URL:
	- Backend API: `http://127.0.0.1:8001/api/`
	- Frontend: `http://127.0.0.1:5173`（使用中なら次の空きポート）

### 注目ポイント

- コア機能: PC構成自動生成とパーツ手動置換のUX
- データ品質: スクレイパーのupsertフローと整合性チェック
- 運用成熟度: タイムアウト付きマイグレーションとPostgreSQLロック診断

### セキュリティ・運用境界

- 運用ツールはローカル管理者専用ユーティリティです。
- これらのスクリプトをHTTPエンドポイント経由で公開しないでください。
- 通常の実行フローには含まれません。必要時に手動で実行してください。

## ドキュメント
- 要件定義: `docs/requirements.md`
- フロントエンド: `frontend/README.md`
- Django: `django/`
- Djangoパッケージ一覧: `django/DJANGO_INSTALLED_PACKAGES.txt`
- FastAPI: `F:\Python\Myportfolio_FastAPI\backend` に移動済み

## プロジェクト分割構成
- FastAPIファイル: `F:\Python\Myportfolio_FastAPI\backend`
- Djangoファイル: `django/`
- FastAPIヘルパースクリプト: `F:\Python\Myportfolio_FastAPI\backend\scripts`

## クイックスタート

### バックエンド（FastAPI）
```bash
cd F:\Python\Myportfolio_FastAPI\backend
python -m uvicorn app.main:app --reload
```
`http://localhost:8000` で起動

### Django
```bash
cd django
python manage.py runserver 8001
```
`http://localhost:8001` で起動

#### PostgreSQLマイグレーション準備（Django）
1. Django依存パッケージをインストール・更新:
```bash
f:/Python/Myportfolio/.venv/Scripts/python.exe -m pip install -r django/django_requirements.txt
```
2. `django/.env.postgresql.example` を参考に `django/.env` を作成してDB値を設定。
	- Windowsでは `DB_CLIENT_ENCODING=UTF8` を維持してpsycopg2デコードエラーを防ぐ。
	- `DJANGO_SECRET_KEY` の設定が必須。生成例:
	  `f:/Python/Myportfolio/.venv/Scripts/python.exe -c "import secrets; print(secrets.token_urlsafe(64))"`
3. マイグレーション実行:
```bash
cd django
f:/Python/Myportfolio/.venv/Scripts/python.exe manage.py migrate
```
4. DB接続確認:
```bash
cd django
f:/Python/Myportfolio/.venv/Scripts/python.exe manage.py showmigrations
```

`DB_ENGINE` が `postgresql` に設定されていない場合、DjangoはSQLiteを使い続けます。

#### PostgreSQLフリーズ対策と診断
運用ツールポリシー（ポートフォリオ範囲）:

- ローカル管理者専用。HTTPエンドポイント経由での公開禁止。
- 手動操作のみ。通常のアプリフローから自動実行しない。
- 共有環境では実行権限を指定オペレーターに限定。
- 本番環境ではデフォルト無効とし、インシデント対応時のみ有効化。

対象ツール:

- `postgres_pg_activity.py`
- `safe_postgres_migrate.ps1`
- `postgres_freeze_watch.ps1`

PostgreSQL使用時は `django/.env` に以下の変数を追加・調整してください:

```bash
DB_CONNECT_TIMEOUT=5
DB_STATEMENT_TIMEOUT_MS=15000
DB_LOCK_TIMEOUT_MS=5000
DB_IDLE_IN_TX_TIMEOUT_MS=10000
```

リポジトリルートからのクイック診断:

```bash
f:/Python/Myportfolio/.venv/Scripts/python.exe postgres_pg_activity.py --action snapshot --env-path django/.env
f:/Python/Myportfolio/.venv/Scripts/python.exe postgres_pg_activity.py --action blockers --env-path django/.env
f:/Python/Myportfolio/.venv/Scripts/python.exe postgres_pg_activity.py --action locks --env-path django/.env
```

タイムアウト付きマイグレーション（VS Codeの長時間フリーズ防止に推奨）:

```powershell
./safe_postgres_migrate.ps1 -TimeoutSec 300 -EnvPath django/.env
```

ワンショット自動アンフリーズモード（タイムアウト → アイドルブロッカー検出 → 終了 → 1回リトライ）:

```powershell
./safe_postgres_migrate.ps1 -TimeoutSec 180 -AutoTerminateIdleBlockers -MinIdleTxSec 30 -RetryTimeoutSec 180 -EnvPath django/.env
```

またはVS Codeタスク `PostgreSQL Safe Migrate` から実行可能。

PowerShellヘルパー（psql使用）:

```powershell
./postgres_pg_activity_tools.ps1 -Action snapshot -EnvPath .\django\.env
./postgres_pg_activity_tools.ps1 -Action blockers -EnvPath .\django\.env
```

継続フリーズウォッチャー（ブロッカー・ロック・スナップショットを繰り返しログファイルに記録）:

```powershell
./postgres_freeze_watch.ps1 -EnvPath django/.env -DurationSec 300 -IntervalSec 2
```

ブロッカーPIDが特定できたら、まずcancelを使い、必要な場合のみterminateを使用:

```bash
f:/Python/Myportfolio/.venv/Scripts/python.exe postgres_pg_activity.py --action cancel --target-pid <PID> --env-path django/.env
f:/Python/Myportfolio/.venv/Scripts/python.exe postgres_pg_activity.py --action terminate --target-pid <PID> --env-path django/.env
```

Windows用ヘルパースクリプト:
- `start_django.bat`
- `start_django.ps1`
- `start_django_frontend.bat`
- `start_django_frontend.ps1`

`start_django_frontend.bat` / `start_django_frontend.ps1` は以下をすべて起動します:
- Djangoサーバー（8001）
- フロントエンド開発サーバー（空きポート自動選択）
- Celery Worker（自動スクレイパー）
- Celery Beat（スケジューラー）

`127.0.0.1:6379` でRedisが起動していない場合、`redis-server` が利用可能であれば自動起動を試みます。

### フロントエンド（React via Vite）
```bash
cd frontend
npm install
npm run dev
```
`http://127.0.0.1:5173` で起動（使用中の場合は次の空きポート）

### フロントエンド（CDN代替 - Node.js不要）
`frontend/index-cdn.html` をブラウザで開くか、以下で配信:
```bash
python -m http.server -d frontend 8080
# http://localhost:8080/index-cdn.html を開く
```