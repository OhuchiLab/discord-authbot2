"""
旧 Bot (discord-authbot) の Firestore のデータを、新 Bot の学生情報 (StudentInfo) に変換する

旧 Bot の Firestore の members コレクションの 1 ドキュメント:

    {"name": "山田 太郎", "student_number": "AB123456", "grade": "M1", "mail": "…@shizuoka.ac.jp", "discordId": "…"}

変換の規則:

- ドキュメント ID をそのまま uuid にする (旧データと突き合わせられるように)
- 学籍番号は大文字、メールアドレスは小文字、学年は新 Bot の学年にそろえる (/register と同じ)
- Discord との紐付けは、Firebase Auth でメール認証が済んでいる人だけ移す
  (旧 Bot は確認メールを送った時点で discordId を保存していたため、discordId があっても認証済みとは限らない)
- 形式が不正な人、学籍番号・メールアドレスが重複する人は、飛ばして理由を報告する
- Discord ID が重複する場合は、後の人の紐付けだけを外して移す
"""

from dataclasses import dataclass, field

from controllers import StudentController
from several_types import Grade, NewStudent, StudentInfo
from utils import normalize_email, normalize_input, normalize_student_number


@dataclass(frozen=True)
class FirebaseMember:
    """
    旧 Bot の Firestore の members コレクションの 1 ドキュメント (値は Firestore に保存されていたまま)

    Attributes:
        doc_id (str): ドキュメント ID
        name, student_number, grade, mail: 各フィールドの値 (無ければ None)
        discord_id: discordId フィールドの値 (無ければ None)
    """

    doc_id: str
    name: object
    student_number: object
    grade: object
    mail: object
    discord_id: object


@dataclass
class MigrationPlan:
    """
    変換した結果

    Attributes:
        students (list[StudentInfo]): 移す学生情報
        skipped (list[str]): 飛ばした人と理由 (例: "doc-3 佐藤 次郎: 学籍番号は英数字 8 文字で…")
        notes (list[str]): 移すが、紐付けを外した人と理由
    """

    students: list[StudentInfo] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


REQUIRED_FIELDS = {"name": "氏名", "student_number": "学籍番号", "grade": "学年", "mail": "メールアドレス"}
"""必須のフィールドと、報告に使う名前"""


def convert(
    members: list[FirebaseMember], verified_emails: set[str], student_controller: StudentController
) -> MigrationPlan:
    """
    Firestore のドキュメントを、新 Bot の学生情報に変換する

    Args:
        members (list[FirebaseMember]): Firestore の members コレクションのドキュメント
        verified_emails (set[str]): Firebase Auth でメール認証が済んでいるメールアドレス (小文字)
        student_controller (StudentController): 移行先の学生情報に対する入力チェックに使う (/register と同じ規則)

    Returns:
        MigrationPlan: 移す学生情報、飛ばした人、紐付けを外した人
    """
    plan = MigrationPlan()

    # 1. 必須のフィールドと学年を確認する
    candidates: list[tuple[FirebaseMember, NewStudent]] = []
    for member in members:
        label = f"{member.doc_id} {_text(member.name) or '(氏名なし)'}"
        missing = [name for key, name in REQUIRED_FIELDS.items() if not _text(getattr(member, key))]
        if missing:
            plan.skipped.append(f"{label}: {', '.join(missing)} がありません")
            continue
        grade = Grade.parse(_text(member.grade))
        if grade is None:
            plan.skipped.append(
                f"{label}: 学年 「{_text(member.grade)}」 は使えません ({Grade.choices_text()} のいずれか)"
            )
            continue
        entry = NewStudent(
            name=_text(member.name), student_number=_text(member.student_number), grade=grade, email=_text(member.mail)
        )
        candidates.append((member, entry))

    # 2. 形式と重複を /register と同じ規則で確認する
    problems = student_controller.find_registration_problems([entry for _, entry in candidates])

    # 3. 学生情報にする (Discord との紐付けは、メール認証済みで重複の無いものだけ)
    used_discord_ids: set[str] = set()
    for index, (member, entry) in enumerate(candidates):
        label = f"{member.doc_id} {normalize_input(entry.name)}"
        if index in problems:
            plan.skipped.append(f"{label}: {problems[index]}")
            continue

        email = normalize_email(entry.email)
        discord_id = _text(member.discord_id) or None
        if discord_id is not None and email not in verified_emails:
            plan.notes.append(f"{label}: メール認証が済んでいないため、未認証として移します (Discord ID {discord_id})")
            discord_id = None
        elif discord_id is not None and discord_id in used_discord_ids:
            plan.notes.append(f"{label}: Discord ID {discord_id} が他の人と重複しているため、未認証として移します")
            discord_id = None
        if discord_id is not None:
            used_discord_ids.add(discord_id)

        plan.students.append(
            StudentInfo(
                uuid=member.doc_id,
                name=normalize_input(entry.name),
                student_number=normalize_student_number(entry.student_number),
                email=email,
                grade=entry.grade,
                discord_id=discord_id,
            )
        )
    return plan


def _text(value: object) -> str:
    """Firestore の値を文字列にする (数値で保存された学籍番号などにも対応)。None は空文字"""
    return "" if value is None else normalize_input(str(value))
