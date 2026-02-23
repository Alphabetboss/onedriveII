import os
import hashlib


def hash_file(path):
    hasher = hashlib.md5()
    with open(path, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()


def delete_duplicates(folder):
    hashes = {}
    deleted = []

    for root, _, files in os.walk(folder):
        for name in files:
            filepath = os.path.join(root, name)
            file_hash = hash_file(filepath)

            if file_hash in hashes:
                print(f"ðŸ—‘ï¸ Deleting duplicate: {filepath}")
                os.remove(filepath)
                deleted.append(filepath)
            else:
                hashes[file_hash] = filepath

    if deleted:
        print(f"\nâœ… Deleted {len(deleted)} duplicates.")
    else:
        print("ðŸŽ‰ No duplicates found.")


# Example usage
target_folder = r"C:\Users\alpha\Desktop\IngeniousIrrigation"
delete_duplicates(target_folder)