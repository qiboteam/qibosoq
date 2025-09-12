#!/usr/bin/env bash

find_deps=$(
	cat <<'EOF'
		/^\]/ { if (s) e=1 }
		s && !e { match($0, /".*"/); print substr($0, RSTART+1, RLENGTH-2) }
		/^dependencies/ { s=1 }
EOF
)
awk "$find_deps" pyproject.toml >qibosoq-requirements.txt

pip install -r qibosoq-requirements.txt
rm qibosoq-requirements.txt

find_path=$(
	cat <<-'EOF'
		import sys

		print([x for x in sys.path if "site-packages" in x][-1])
	EOF
)
env_path=$(python3 -c "$find_path")
project_dir=$(dirname "$0")
package_path=$(realpath "$project_dir")/src

echo "$package_path" >"$env_path/qibosoq.pth"
