target_time="2025-11-23 15:38:53"
start_ts=$(date -d "$target_time -10 seconds" +%s)
end_ts=$(date -d "$target_time +10 seconds" +%s)

awk -v start="$start_ts" -v end="$end_ts" '
{
  if (match($0, /([0-9]{4}-[0-9]{2}-[0-9]{2}) ([0-9]{2}:[0-9]{2}:[0-9]{2})/, parts)) {
    split(parts[1], d, "-");
    split(parts[2], t, ":");
    ts = mktime(d[1] " " d[2] " " d[3] " " t[1] " " t[2] " " t[3]);
    if (ts >= start && ts <= end) print $0;
  }
}' access.log
