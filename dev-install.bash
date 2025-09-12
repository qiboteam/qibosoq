prog=$(
	cat <<'EOF'
		/^\]/ { if (s) e=1 }
		s && !e { match($0, /".*"/); print substr($0, RSTART+1, RLENGTH-2) }
		/^dependencies/ { s=1 }
EOF
)
awk "$prog" pyproject.toml >qibosoq-requirements.txt

pip install -r qibosoq-requirements.txt
rm qibosoq-requirements.txt
