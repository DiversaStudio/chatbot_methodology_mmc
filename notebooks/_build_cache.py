import sys; sys.path.insert(0, "src")
import mmc_data, mmc_nlp
m = mmc_data.load_messages()
msgs = list(m["message"])
print("messages:", len(msgs))
mmc_nlp.embed_messages(msgs)
mmc_nlp.zeroshot_tint(msgs)
mmc_nlp.emotion_label(msgs)
print("caches built")
