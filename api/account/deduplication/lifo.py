# --> LIFO deduplication
def lifo(lifo_passport, lifo_db_stamps):
  deduped_passport = lifo_passport
  for stamp in deduped_passport["stamps"]:
      stamp_hash = stamp["credential"]["credentialSubject"]["hash"]
      if any(db_stamp.hash == stamp_hash for db_stamp in lifo_db_stamps):
          deduped_passport["stamps"].remove(stamp)

  return deduped_passport

