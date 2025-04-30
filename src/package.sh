# Create (or overwrite) the big file
output="royal_siege_all_sources.txt"
: > "$output"          # truncate / create

# Walk the tree and append each .py file, preceded by a header
find . -type f -name '*.py' -print0 | sort -z | while IFS= read -r -d '' file; do
  printf '##### %s #####\n' "$file" >> "$output"   # header line with filename
  cat "$file"                      >> "$output"    # file contents
  printf '\n\n'                    >> "$output"    # blank line between files
done

