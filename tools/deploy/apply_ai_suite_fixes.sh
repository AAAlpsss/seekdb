#!/usr/bin/env bash
# Run from a host terminal: preserve the existing single deployment and its data.
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "$script_dir/../.." && pwd)
instance_dir=/home/stardust/obtest/seekdb1
build_bin="$repo_root/build_release/src/observer/seekdb"
cd "$script_dir"
ulimit -Sn 65536

# A saved PID in a backup directory is not an instance. Validate live processes.
mapfile -t live_pids < <(pgrep -x 'seekdb|observer' || true)
if [[ ${#live_pids[@]} -ne 1 ]]; then
  printf 'Expected exactly one live database, found %s. No changes made.\n' "${#live_pids[@]}" >&2
  exit 1
fi
instance_pid=$(cat "$instance_dir/run/seekdb.pid")
if [[ ${live_pids[0]} != "$instance_pid" || $(readlink -f "/proc/$instance_pid/exe") != "$instance_dir/bin/seekdb" ]]; then
  echo 'The live database does not match the persistent single deployment. No changes made.' >&2
  exit 1
fi
if [[ ! -x "$build_bin" ]]; then
  echo 'Build build_release/src/observer/seekdb first.' >&2
  exit 1
fi
for source in \
  "$repo_root/src/rootserver/ob_ddl_service.cpp" \
  "$repo_root/src/observer/ai_service/ob_ai_service_proxy.cpp" \
  "$repo_root/src/share/ai_service/ob_ai_service_struct.cpp" \
  "$repo_root/src/share/ai_service/ob_ai_service_struct.h" \
  "$repo_root/src/share/inner_table/ob_inner_table_schema_def.py" \
  "$repo_root/src/sql/engine/expr/ob_expr_ai/ob_expr_ai_complete.cpp" \
  "$repo_root/src/sql/engine/expr/ob_expr_ai/ob_ai_func_utils.cpp"; do
  if [[ "$source" -nt "$build_bin" ]]; then
    echo 'The build is older than the fixes. Complete the build before applying.' >&2
    exit 1
  fi
done
printf 'Verified one live instance: single, PID %s, %s\n' "$instance_pid" "$instance_dir"

backup_dir="/home/stardust/obtest/deployment-backups/ai-suite-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_dir"
cp --reflink=auto "$instance_dir/bin/seekdb" "$backup_dir/seekdb"
cp "$script_dir/.obd/cluster/single/config.yaml" "$backup_dir/config.yaml"
./obd.sh stop -n single
if kill -0 "$instance_pid" 2>/dev/null; then
  echo 'Database is still running; binary replacement was cancelled.' >&2
  exit 1
fi
cp --reflink=auto "$build_bin" "$instance_dir/bin/seekdb.new"
mv "$instance_dir/bin/seekdb.new" "$instance_dir/bin/seekdb"
# Keep the deployment mirror input in sync with the installed executable.
cp --reflink=auto "$build_bin" "$script_dir/bin/seekdb"
./obd.sh start -n single
"$repo_root/deps/3rd/u01/obclient/bin/obclient" --no-defaults -h127.0.0.1 -P10000 -uroot -e 'SELECT VERSION();'
python3 ./upgrade_ai_endpoint.py
./obd.sh mysqltest -n single --disable-reboot --suite ai_function
