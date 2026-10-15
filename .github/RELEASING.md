# CIとPyPIリリースの運用

この手順はリポジトリの保守者向けです。通常のpush / pull requestは
`.github/workflows/ci.yml`、`v*`タグのpushは
`.github/workflows/release.yml`から、**同じ**再利用可能な
`.github/workflows/checks.yml`を呼び出します。タグに対しても検証は
再実行され、検証済みのwheelとsdistだけが公開ジョブへ渡されます。

## 公開前にGitHub / PyPI側で必要な設定

1. GitHubリポジトリに `pypi` Environmentを作成します。必要に応じて
   保守者の承認（Required reviewers）を設定し、Deployment branches/tagsを
   リリース用タグに制限します。リリースタグの作成権限も保護します。
2. PyPIの `pyinto` プロジェクトのTrusted Publisherに、**実際の**
   GitHubオーナー名とリポジトリ名、Workflow filename `release.yml`、
   Environment name `pypi` を登録します。初回公開前は、PyPIの
   Pending Publisherを利用できます（プロジェクト名の利用可否も確認してください）。
3. APIトークンをGitHub Secretsへ保存する必要はありません。OIDC権限
   `id-token: write` は公開ジョブにのみ設定してあります。

## 実施手順

1. `pyproject.toml` の `project.version` を公開予定バージョンにします。
   README、仕様・英語公開文書の同期と、すべてのCIチェックを完了します。
2. 対象コミットに `v<project.version>` のタグを付けてpushします。
   例: バージョン `0.2.0` なら `v0.2.0`。
3. `Release to PyPI` ワークフローが同じ品質ゲートを再実行します。
   いずれかのテスト・文書・ビルド検証、またはタグとバージョンの照合に
   失敗した場合、公開ジョブは実行されません。
4. 必要なEnvironment承認の後、Trusted PublishingでPyPIへ提出します。
   公開ジョブはソースをチェックアウトせず再ビルドも行いません。

`python scripts/verify_release.py v0.2.0` でタグとバージョンの照合を
ローカル確認できます。GitHub Actionsの実行とPyPI側の接続検証は、実際の
GitHub/PyPI環境で初めて確定します。このリポジトリの変更だけでは
Trusted Publisherの登録やPyPIへの公開は完了しません。
