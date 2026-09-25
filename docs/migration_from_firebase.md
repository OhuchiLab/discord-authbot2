# 旧 Bot (Firebase) からの移行手順

旧 Bot ([discord-authbot](https://github.com/OhuchiLab/discord-authbot)) が Firebase (Firestore) に保存していた学生情報を、
新 Bot の学生情報ファイル (`data/students.msgpack`) に移す手順です。1 回だけ行います。

移行ツール: [tools/firebase_migration/](../tools/firebase_migration/)

---

## 1. 移行されるもの

| 旧 Bot (Firestore の `members` コレクション) | 新 Bot の学生情報 | 備考 |
| --- | --- | --- |
| ドキュメント ID | uuid | そのまま使う (旧データと突き合わせられるように) |
| `name` | 氏名 | |
| `student_number` | 学籍番号 | 大文字にそろえる |
| `grade` | 学年 | `m1` → `M1` のようにそろえる |
| `mail` | メールアドレス | 小文字にそろえる |
| `discordId` | Discord との紐付け | **Firebase Auth でメール認証が済んでいる人だけ** 移す |

### Discord との紐付けについて

旧 Bot は、確認メールを送った時点で `discordId` を保存していました。そのため `discordId` があっても、
メール認証を済ませていない (= 認証が完了していない) 人が含まれます。
移行ツールは Firebase Auth で **メール認証が済んでいる人だけ** を認証済みとして移し、それ以外の人は未認証として移します。
未認証として移した人は、新 Bot で `/auth` を実行してもう一度認証してもらいます。

### 移されない人

次の人は飛ばして、理由を報告します。移行後に `/register` や `/edit_student` で直してください。

- 氏名・学籍番号・学年・メールアドレスのどれかが無い
- 形式が不正 (学籍番号が英数字 8 文字でない、メールアドレスが `@shizuoka.ac.jp` でない、学年が不明)
- 学籍番号かメールアドレスが、先に移す人と重複している

Discord ID だけが他の人と重複している場合は、後の人の紐付けだけを外して (未認証として) 移します。

## 2. 準備

1. **旧 Bot を止める。** 両方の Bot が動いていると、参加や DM に両方が反応してしまいます。
2. **新 Bot を止める** (動かしている場合)。`sudo systemctl stop authbot` または `Ctrl+C`。
3. **サービスアカウントの鍵を用意する。**
   Firebase コンソール > プロジェクトの設定 > サービス アカウント > 「新しい秘密鍵を生成」で JSON ファイルをダウンロードする。
   旧 Bot で使っていた `ohuchilab-discord-firebase-adminsdk-….json` が残っていれば、それを使ってもよい。
   - ⚠️ 鍵は Firebase を自由に操作できる秘密情報です。**リポジトリの外** (例: `~/keys/`) に置き、コミットしないこと。
     (`.gitignore` にも `*firebase-adminsdk*.json` を入れてあります)
4. **移行ツールに必要なライブラリを入れる。**
   ```shell
   cd ~/discord-authbot2
   source .venv/bin/activate
   pip install -r requirements-migration.txt
   ```

## 3. 移行

### 3.1 確認する (何も書き込まない)

```shell
python -m tools.firebase_migration --credentials ~/keys/ohuchilab-discord-firebase-adminsdk-xxxx.json
```

表示の例:

```text
Firestore の学生情報: 32 件
移す人: 31 人 (認証済み 27 人 / 未認証 4 人)
飛ばす人: 1 人
　Xa9f… 佐藤 次郎: 学籍番号は英数字 8 文字で入力してください。
紐付けを外して移す人: 2 人
　b71c… 鈴木 花子: メール認証が済んでいないため、未認証として移します (Discord ID 1234…)

確認だけ行い、何も書き込んでいません。内容に問題が無ければ --apply を付けて実行してください。
```

内容を確認します。飛ばす人が多い場合は、Firestore 側を直してから、もう一度確認してもよいです。

### 3.2 書き込む

```shell
python -m tools.firebase_migration --credentials ~/keys/ohuchilab-discord-firebase-adminsdk-xxxx.json --apply
```

- 移行先 (`data/students.msgpack`) にすでに学生情報がある場合は、データが混ざらないよう何もせずに終了します。
- 書き込んだ直後の状態は `data/backups/` にバックアップされます。
- 学生情報ファイルの場所を変えている場合は `--database`、バックアップの場所を変えている場合は `--backup-dir` を指定します
  (`python -m tools.firebase_migration --help` で一覧を見られます)。
- Firestore と Firebase Auth は読み込むだけで、変更しません。

## 4. 移行後

1. **新 Bot を起動する** (`sudo systemctl start authbot` または `python -m authbot`)。
2. **`/list_students` で確認する。** `status:未認証` で絞り込むと、もう一度認証が必要な人がわかります。
3. **未認証として移した人に `/auth` を実行してもらう。**
4. **ロールについて**: 新 Bot は旧 Bot と同じ名前のロール (`Authorized` / `Unauthorized` / `Grade:*` / `Administrator`) を使うため、
   認証済みの人のロールはそのまま使えます。付け直したいときは、本人に `/auth` を実行してもらうと付け直されます。
5. **鍵を片付ける。** 移行が終わったら鍵のファイルを削除し、Firebase コンソールでその鍵を無効にしてください。
6. 旧 Bot と Firebase プロジェクトを止める・消すのは、新 Bot で問題なく運用できることを確かめてからにしてください。
