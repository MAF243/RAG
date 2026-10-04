from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st

KINDS = {
    "chat": "Percakapan",
    "explain": "Penjelasan",
    "summary": "Rangkuman",
    "flashcards": "Flashcard",
    "quiz": "Latihan soal",
}


def unique_label(key, entries, label):
    value = label(entries[key])
    duplicates = sum(label(item) == value for item in entries.values())
    return f"{value} · #{key[:6]}" if duplicates > 1 else value


def date_label(value):
    return (
        datetime.fromisoformat(value)
        .astimezone(ZoneInfo("Asia/Jakarta"))
        .strftime("%d/%m/%Y %H:%M WIB")
    )


def show_sources(references):
    if references:
        with st.expander("Periksa sumber dan halaman"):
            for ref in references:
                st.write(f"[{ref['id']}] {ref['source']} · halaman {ref['page']}")
                st.text(ref["text"])


def show_message(message):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        show_sources(message.get("referensi", []))


def export_markdown(item):
    lines = [
        f"# {item['title']}",
        "",
        f"Jenis: {KINDS[item['kind']]}",
        f"Disimpan: {item['created_at']}",
        "",
    ]
    if item["kind"] == "chat":
        for message in item["payload"]["messages"]:
            lines.extend([f"## {message['role']}", message["content"], ""])
            for ref in message.get("referensi", []):
                lines.extend(
                    [f"[{ref['id']}] {ref['source']} — halaman {ref['page']}", ref["text"], ""]
                )
    else:
        payload = item["payload"]
        content = payload["content"]
        coverage = payload["coverage"]
        lines.append(
            f"Cakupan: {coverage['selected_chunks']} dari {coverage['total_chunks']} potongan teks hasil ekstraksi."
        )
        for section in content.get("sections", []):
            lines.extend(
                [
                    f"## {section['heading']}",
                    section["body"],
                    "Sumber: " + ", ".join(section["source_ids"]),
                    "",
                ]
            )
        for index, card in enumerate(content.get("cards", []), 1):
            lines.extend(
                [
                    f"## Kartu {index}: {card['front']}",
                    card["back"],
                    "Sumber: " + ", ".join(card["source_ids"]),
                    "",
                ]
            )
        for index, question in enumerate(content.get("questions", []), 1):
            lines.append(f"## Soal {index}: {question['question']}")
            lines.extend(f"{chr(65 + i)}. {option}" for i, option in enumerate(question["options"]))
        if item.get("latest_attempt"):
            lines.extend(["", f"Skor percobaan terakhir: {item['latest_attempt']['score']}%"])
            for feedback in item["latest_attempt"]["feedback"]:
                lines.append(
                    f"Soal {feedback['question_index'] + 1}: jawaban {chr(65 + feedback['correct_index'])}. {feedback['explanation']}"
                )
        lines.extend(["", "## Sumber"])
        for ref in payload["references"]:
            lines.extend(
                [f"[{ref['id']}] {ref['source']} — halaman {ref['page']}", ref["text"], ""]
            )
    if item["notes"]:
        lines.extend(["## Catatan pribadi", item["notes"]])
    return "\n".join(lines)


def show_learning_item(item, call_api, refresh_item):
    st.subheader(item["title"])
    st.caption(f"{KINDS[item['kind']]} · {date_label(item['created_at'])}")
    if item["kind"] == "chat":
        for message in item["payload"]["messages"]:
            show_message(message)
    else:
        payload = item["payload"]
        coverage = payload["coverage"]
        if not coverage["complete"]:
            st.info(
                f"Bahan ini memakai {coverage['selected_chunks']} dari {coverage['total_chunks']} potongan teks. Cakupannya terbatas; pilih topik khusus untuk mempelajari bagian lain."
            )
        else:
            st.caption("Seluruh potongan teks hasil ekstraksi terpilih masuk ke konteks belajar.")
        st.caption(
            " · ".join(
                f"{page['source']}: hal. {', '.join(map(str, page['pages']))}"
                for page in coverage["pages"]
            )
        )
        content = payload["content"]
        if item["kind"] in ("explain", "summary"):
            for section in content["sections"]:
                st.markdown(f"#### {section['heading']}")
                st.markdown(section["body"])
                st.caption(
                    "Sumber: " + ", ".join(f"[{source}]" for source in section["source_ids"])
                )
        elif item["kind"] == "quiz":
            st.write(
                "Coba jawab sendiri terlebih dahulu. Pembahasan tampil setelah semua soal dijawab."
            )
            with st.form(f"quiz-{item['id']}"):
                answers = []
                for index, question in enumerate(content["questions"]):
                    answer = st.radio(
                        f"{index + 1}. {question['question']}",
                        range(4),
                        format_func=lambda option, choices=question["options"]: (
                            f"{chr(65 + option)}. {choices[option]}"
                        ),
                        index=None,
                        key=f"answer-{item['id']}-{index}",
                    )
                    answers.append(answer)
                submitted = st.form_submit_button("Periksa jawaban")
            if submitted:
                if any(answer is None for answer in answers):
                    st.warning("Jawab semua soal terlebih dahulu.")
                elif call_api(
                    "POST", f"/study/items/{item['id']}/attempts", json={"answers": answers}
                ):
                    refresh_item(item["id"])
                    st.rerun()
            if attempt := item.get("latest_attempt"):
                st.metric(
                    "Skor percobaan terakhir",
                    f"{attempt['score']:g}%",
                    f"{attempt['correct']} dari {attempt['total']} benar",
                    delta_color="off",
                )
                st.caption(
                    f"Diperiksa {date_label(attempt['created_at'])}. Ini skor latihan, bukan nilai resmi atau ukuran pasti penguasaan materi."
                )
                for result in attempt["feedback"]:
                    with st.expander(
                        f"Soal {result['question_index'] + 1} · {'Benar' if result['correct'] else 'Perlu diulang'}"
                    ):
                        st.write(
                            f"Pilihanmu: {chr(65 + result['selected_index'])} · Kunci latihan: {chr(65 + result['correct_index'])}"
                        )
                        st.write(result["explanation"])
                        st.caption("Sumber: " + ", ".join(result["source_ids"]))
        elif item["kind"] == "flashcards":
            cards = content["cards"]
            reviews = {row["card_index"]: row for row in item["reviews"]}
            only_due = st.checkbox("Hanya kartu yang perlu diulang", key=f"due-{item['id']}")
            now = datetime.now(timezone.utc).isoformat()
            indices = [
                i
                for i in range(len(cards))
                if not only_due or i not in reviews or reviews[i]["due_at"] <= now
            ]
            if not indices:
                st.success("Kartu di set ini sudah diulas. Buka lagi sesuai jadwal pengulangan.")
            else:
                index = st.selectbox(
                    "Kartu",
                    indices,
                    format_func=lambda i: f"Kartu {i + 1} dari {len(cards)}",
                    key=f"card-{item['id']}-{only_due}",
                )
                st.markdown(f"### {cards[index]['front']}")
                st.caption("Coba ingat jawabannya sebelum membuka kartu.")
                with st.expander("Buka jawaban kartu"):
                    st.write(cards[index]["back"])
                    st.caption("Sumber: " + ", ".join(cards[index]["source_ids"]))
                if index in reviews:
                    st.caption("Ulangi pada " + date_label(reviews[index]["due_at"]))
                for column, rating, label in zip(
                    st.columns(3),
                    ["again", "good", "easy"],
                    ["Belum ingat", "Sudah ingat", "Mudah"],
                ):
                    if column.button(label, key=f"review-{item['id']}-{index}-{rating}"):
                        if call_api(
                            "POST",
                            f"/study/items/{item['id']}/reviews",
                            json={"card_index": index, "rating": rating},
                        ):
                            refresh_item(item["id"])
                            st.rerun()
                st.caption(
                    "Jadwal ini mengikuti penilaianmu sendiri. “Belum ingat” dijadwalkan kembali 10 menit lagi."
                )
        show_sources(payload["references"])
    with st.expander("Catatan pribadi dan unduh hasil"):
        notes = st.text_area(
            "Tulis dengan bahasamu sendiri",
            value=item["notes"],
            key=f"notes-{item['id']}",
            max_chars=8000,
        )
        if st.button("Simpan catatan", key=f"save-notes-{item['id']}"):
            if call_api("PATCH", f"/study/items/{item['id']}/notes", json={"notes": notes}):
                item["notes"] = notes
                st.success("Catatan tersimpan.")
        st.download_button(
            "Unduh Markdown",
            export_markdown(item),
            file_name=f"belajar-{item['id'][:8]}.md",
            mime="text/markdown",
            key=f"download-{item['id']}",
        )
