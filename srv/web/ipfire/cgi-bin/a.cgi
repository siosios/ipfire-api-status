#!/usr/bin/perl
###############################################################################
# HA-IPFire GUI Display – Final Clean Version
# Place at: /srv/web/ipfire/cgi-bin/a.cgi
###############################################################################

use strict;
use warnings;
use JSON::PP ();

# ---------------------------------------------------------------------------
# 1. Load IPFire Core Libraries (MUST be first)
# ---------------------------------------------------------------------------
require '/var/ipfire/general-functions.pl';
require "${General::swroot}/lang.pl";
require "${General::swroot}/header.pl";
require '/opt/pakfire/lib/functions.pl';
require '/var/ipfire/haipfire_lib.pl';

# Import only what we need from our shared lib
Haipfire::Lib->import(qw( read_file traffic_data ));
my $hostname;
my $swroot;
my %settings;
%settings = ();
# ---------------------------------------------------------------------------
# 2. Constants & Configuration
# ---------------------------------------------------------------------------
my $API_SCRIPT = "/srv/web/ipfire/cgi-bin/api.cgi";
my $JP         = JSON::PP->new->utf8->canonical;
my %pppsettings = ();
&General::readhash("${General::swroot}/ppp/settings", \%pppsettings);
my $data;
&General::readhash("${General::swroot}/main/settings", \%settings);
$hostname = $settings{'HOSTNAME'};

# ---------------------------------------------------------------------------
# 3. Helper Subroutines (defined early so we can use them below)
# ---------------------------------------------------------------------------

sub html_escape {
    my ($v) = @_;
    return '' unless defined $v;
    $v =~ s/&/&amp;/g;
    $v =~ s/"/&quot;/g;
    $v =~ s/</&lt;/g;
    $v =~ s/>/&gt;/g;
    return $v;
}

sub esc { return html_escape($_[0]); }

sub hash_ref {
    return ref($_[0]) eq 'HASH' ? $_[0] : {};
}

sub array_ref {
    return ref($_[0]) eq 'ARRAY' ? $_[0] : [];
}

sub g {
    my ($hr, $k, $def) = @_;
    return $def unless ref($hr) eq 'HASH';
    return exists $hr->{$k} ? $hr->{$k} : $def;
}

sub is_true {
    my ($v) = @_;
    return (defined $v && ($v eq '1' || $v eq 'true' || $v == 1 || $v eq 'true')) ? 1 : 0;
}

sub yn  { return is_true($_[0]) ? esc(("Yes"))    : esc(("No")); }
sub rs  { return is_true($_[0]) ? esc(("Running")) : esc(("Stopped")); }
sub en  { return is_true($_[0]) ? esc(("Enabled")) : esc(("Disabled")); }

sub fmt_bytes {
    my ($b) = @_; $b = 0 unless defined $b && $b =~ /^\d+$/;
    my @u = qw(B KB MB GB TB PB); my $i = 0;
    while ($b >= 1024 && $i < $#u) { $b /= 1024; $i++; }
    return $i ? sprintf("%.1f %s", $b, $u[$i]) : "$b B";
}

sub fmt_time {
    my ($s) = @_; $s = 0 unless defined $s && $s =~ /^\d+$/;
    my @p;
    my $d = int($s/86400); $s %= 86400; push @p, "$d d" if $d;
    my $h = int($s/3600);  $s %= 3600;  push @p, "$h h" if $h;
    my $m = int($s/60);    $s %= 60;    push @p, "$m m" if $m;
    push @p, "$s s" if $s || !@p;
    return join ', ', @p;
}

sub fmt_since {
    my ($ts) = @_;
    $ts = 0 unless defined $ts && $ts =~ /^\d+$/;
    my $now = time();
    my $diff = $now - $ts;
    $diff = 0 if $diff < 0;
    $diff = int($diff);

    my $years = int($diff / 31536000);       # 365 * 86400
    $diff %= 31536000;
    my $months = int($diff / 2592000);       # 30 * 86400
    $diff %= 2592000;
    my $days = int($diff / 86400);
    $diff %= 86400;
    my $hours = int($diff / 3600);
    $diff %= 3600;
    my $minutes = int($diff / 60);
    my $seconds = $diff % 60;

    my @p;
    push @p, "$years y" if $years;
    push @p, "$months mo" if $months;
    push @p, "$days d" if $days;
    push @p, "$hours h" if $hours;
    push @p, "$minutes m" if $minutes;
    push @p, "$seconds s" if $seconds || !@p;

    return join ', ', @p;
}

sub status_badge {
    my ($txt) = @_; $txt //= 'unknown';
    my $cls = 'off';
    $cls = 'on'  if $txt =~ /^(connected|running|enabled)$/i;
    $cls = 'warn' if $txt eq 'connecting';
    return "<span class='ha-badge $cls'>" . esc($txt) . "</span>";
}

# Prints the embedded <style> block
sub print_css {
    print <<'END_CSS';
<style>
/* --- HA-IPFire Dashboard Styles --- */
.ha-page { display: grid; gap: 1rem; padding: 0.5rem; }
.ha-topbar { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem; margin-bottom: 0.5rem; }
.ha-title { margin: 0; font-size: 1.5rem; font-weight: 700; color: #1f2937; }
.ha-subtitle { margin: 0.25rem 0 0; color: #6b7280; font-size: 0.9rem; }
.ha-pill { background: #e0e7ff; color: #3730a3; padding: 0.3rem 0.8rem; border-radius: 999px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }
.ha-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; }
.ha-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 1.25rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
.ha-card h3 { margin: 0 0 1rem; font-size: 1.1rem; color: #111827; border-bottom: 1px solid #f3f4f6; padding-bottom: 0.5rem; }
.ha-table { display: grid; grid-template-columns: 140px 1fr; gap: 0.5rem 1rem; margin: 0; }
.ha-table dt { color: #6b7280; font-weight: 600; font-size: 0.875rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ha-table dd { margin: 0; color: #111827; font-weight: 600; font-size: 0.875rem; text-align: right; word-break: break-all; }
.ha-traffic-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 0.75rem; margin-bottom: 1rem; }
.ha-traffic-box { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 10px; padding: 1rem; text-align: center; }
.ha-traffic-box .label { display: block; color: #6b7280; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.25rem; }
.ha-traffic-box .value { display: block; color: #111827; font-size: 1.5rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.ha-badge { display: inline-flex; align-items: center; border-radius: 999px; padding: 0.2rem 0.6rem; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em; }
.ha-badge.on   { background: #dcfce7; color: #166534; }
.ha-badge.warn { background: #fef3c7; color: #92400e; }
.ha-badge.off  { background: #fee2e2; color: #991b1b; }
.ha-alert { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; padding: 1rem; border-radius: 8px; font-weight: 600; margin-bottom: 1rem; }
.ha-muted { color: #9ca3af; font-size: 0.875rem; text-align: center; padding: 1rem; }
</style>
END_CSS
}

# Fetch JSON from API script (via command line to avoid HTTP loop)
sub fetch_api_json {
    # Use $^X (current perl) to execute the api script directly
    my @out = General::system_output($^X, $API_SCRIPT);
    my $raw = join('', @out);

    # Strip HTTP Headers (everything before first {)
    my $start = index($raw, '{');
    my $end   = rindex($raw, '}');
    return undef if $start == -1 || $end == -1 || $end <= $start;
    return substr($raw, $start, $end - $start + 1);
}

# Render a definition list from array of [label, value]
sub render_rows {
    my ($rows) = @_;
    print "<dl class='ha-table'>\n";
    foreach my $r (@$rows) {
        next unless ref $r eq 'ARRAY' && @$r >= 2;
        print "<dt>" . esc($r->[0]) . "</dt><dd>" . esc($r->[1]) . "</dd>\n";
    }
    print "</dl>\n";
}

# Standardized Error Page (prints headers first)
sub render_error {
    my ($msg) = @_;
    &Header::showhttpheaders();          # <--- CRITICAL: HEADERS FIRST
    &Header::openpage((''), 1, '');
    &Header::openbigbox('100%', 'left', '', '');
    &Header::openbox('100%', 'left', ('IPFire Status'));
    print "<div class='ha-page'>\n";
    print_css();
    print "<div class='ha-alert'>" . esc($msg) . "</div>\n";
    print "</div>\n";
    &Header::closebox();
    &Header::closebigbox();
    &Header::closepage();
    exit 0;
}

# ---------------------------------------------------------------------------
# 4. MAIN EXECUTION FLOW
# ---------------------------------------------------------------------------

# ---- 4a. Print HTTP Headers & Page Start IMMEDIATELY ----
# If we die after this, browser gets a partial page instead of 500.
&Header::showhttpheaders();
&Header::openpage((''), 1, '');
&Header::openbigbox('100%', 'left', '', '');
&Header::openbox('100%', 'left', (''));

print "<div class='ha-page'>\n";
print_css();

# ---- 4b. Fetch & Parse JSON ----
my $raw_json = fetch_api_json();
unless (defined $raw_json) {
    render_error("API returned empty or invalid response.");
}


eval { $data = $JP->decode($raw_json); };
if ($@ || ref $data ne 'HASH') {
    render_error("JSON Parse Error: " . esc($@));
}

if (exists $data->{error}) {
    render_error("API Error: " . esc($data->{error} // 'unknown'));
}

my $external_ip = read_file("${General::swroot}/red/local-ipaddress");
my $external_hostname = '';

if ($external_ip ne '') {
    $external_hostname =
        (gethostbyaddr(pack("C4", split(/\./, $external_ip)), 2))[0]
        || '';
}

my $profile = $pppsettings{'PROFILENAME'} // '';

# ---- 4c. Extract Data Sections (Safe defaults) ----
my $sys   = (ref $data->{system}     eq 'HASH') ? $data->{system}     : {};
my $net   = (ref $data->{network}    eq 'HASH') ? $data->{network}    : {};
my $svc   = (ref $data->{services}   eq 'HASH') ? $data->{services}   : {};
my $addons= (ref $data->{addons}     eq 'ARRAY') ? $data->{addons}     : [];
my $traf  = (ref $data->{traffic}    eq 'HASH') ? $data->{traffic}    : {};
my $conn  = (ref $data->{connection} eq 'HASH') ? $data->{connection} : {};

# ---- 4d. Traffic Fallback (if API gave 0/undef) ----
my $rx = $traf->{rx_bytes};
my $tx = $traf->{tx_bytes};

# Validate API traffic
my $api_ok = (defined $rx && $rx =~ /^\d+$/ && defined $tx && $tx =~ /^\d+$/);

if (!$api_ok) {
    # Fallback to local sysfs read via shared lib
    ($rx, $tx) = traffic_data();
}

$rx = 0 unless defined $rx && $rx =~ /^\d+$/;
$tx = 0 unless defined $tx && $tx =~ /^\d+$/;
$rx = int($rx); $tx = int($tx);
my $total = $rx + $tx;
my $iface = read_file('/var/ipfire/red/iface') // 'unknown';

# ---- 4e. Render Top Bar ----
print "<div class='ha-topbar'>";
print "<div><h1 class='ha-title'>" . esc(('IPFire Status')) . "</h1>";
print "<p class='ha-subtitle'>" . esc(('Live status from HA-IPFire API')) . "</p></div>";
print "<span class='ha-pill'>API v" . esc($data->{api_version} // '1') . "</span>";
print "</div>\n";

# ---- 4f. Render Grid ----
print "<div class='ha-grid'>\n";

# --- CARD 1: System ---
print "<section class='ha-card'><h3>" . esc(('System Information')) . "</h3>";
my $since_ts  = $conn->{connected_since} // 0;
# fireinfo_data() returns memory/root_size in KiB, not bytes.
my $memory_kib = $sys->{memory} // 0;
my $root_kib   = $sys->{root_size} // 0;

$memory_kib = 0 unless defined $memory_kib && $memory_kib =~ /^\d+$/;
$root_kib   = 0 unless defined $root_kib   && $root_kib   =~ /^\d+$/;

# Display as GiB / TiB for readable values
my $memory_gib = sprintf("%.1f", $memory_kib / 1024 / 1024);
my $root_tib   = sprintf("%.2f", $root_kib   / 1024 / 1024 / 1024);

render_rows([
    ['Version',            $sys->{version}           // 'N/A'],
    ['Pakfire Version',    $sys->{pakfire_version}   // 'N/A'],
    ['Kernel Version',     $sys->{kernel_version}    // 'N/A'],
    ['Architecture',       $sys->{architecture}      // 'N/A'],
    ['CPU Model',          $sys->{cpu_model}         // 'N/A'],
    ['CPU Count',          $sys->{cpu_count}         // 0],
    ['Model',              $sys->{model}             // 'N/A'],
    ['Vendor',             $sys->{vendor}            // 'N/A'],
	['Memory (GiB)',       $memory_gib],
	['Root Size (TiB)',    $root_tib],
    ['Virtual Machine',    yn($sys->{virtual})],
    ['Core Update Avail.', yn($sys->{core_update})],
    ['Package Updates',    $sys->{package_updates}   // 0],
]);
print "</section>\n";

# --- CARD 2: Network Interfaces ---
print "<section class='ha-card'><h3>" . esc(('Network Interfaces')) . "</h3>";
render_rows([
    ['Blue',   en($net->{blue})],
    ['Green',  en($net->{green})],
    ['Orange', en($net->{orange})],
    ['Red',    en($net->{red})],
]);
print "</section>\n";

# --- CARD 3: Services ---
print "<section class='ha-card'><h3>" . esc(('Services Status')) . "</h3>";
my @svc_order = qw(dhcp web_server cron dns_resolver logging ntp ssh vpn web_proxy ips ovpn_roadwarrior lldp dbus);
my @svc_rows;
foreach my $k (@svc_order) {
    my $label = $k; $label =~ s/_/ /g; $label = ucfirst($label);
    $label = ("IPS")              if $k eq 'ips';
    $label = ("OpenVPN Roadwarrior") if $k eq 'ovpn_roadwarrior';
    $label = ("LLDP")             if $k eq 'lldp';
    $label = ("DBus")             if $k eq 'dbus';
    push @svc_rows, [ $label, rs($svc->{$k}) ];
}
render_rows(\@svc_rows);
print "</section>\n";

# --- CARD 4: Add-ons ---
print "<section class='ha-card'><h3>" . esc(('Add-ons Status')) . "</h3>";
if (@$addons) {
    my @addon_rows;
    foreach my $a (@$addons) {
        next unless ref $a eq 'HASH';
        push @addon_rows, [ $a->{name} // 'Unknown', rs($a->{running}) ];
    }
    render_rows(\@addon_rows) if @addon_rows;
    print "<p class='ha-muted'>" . esc(('No add-on services found.')) . "</p>" unless @addon_rows;
} else {
    print "<p class='ha-muted'>" . esc(('No add-ons with services detected.')) . "</p>";
}
print "</section>\n";

# --- CARD 5: Network Traffic (Visual + Table) ---
print "<section class='ha-card'><h3>" . esc(('Network Traffic')) . "</h3>";
print "<div class='ha-traffic-grid'>";
print "<div class='ha-traffic-box'><span class='label'>" . esc(('Received')) . "</span><span class='value'>" . esc(fmt_bytes($rx)) . "</span></div>";
print "<div class='ha-traffic-box'><span class='label'>" . esc(('Transmitted')) . "</span><span class='value'>" . esc(fmt_bytes($tx)) . "</span></div>";
print "<div class='ha-traffic-box'><span class='label'>" . esc(('Total')) . "</span><span class='value'>" . esc(fmt_bytes($total)) . "</span></div>";
print "</div>";
render_rows([
    ['Interface',   $iface],
    ['RX Bytes',    $rx],
    ['TX Bytes',    $tx],
    ['Total Bytes', $total],
]);
print "</section>\n";
# -----------------------------------------------------------------
# 4e.  Get *current* RED traffic speed (Mbit/s)
# -----------------------------------------------------------------
sub get_red_speed {
    # Determine the interface name (red0, red1, …)
    my $iface = read_file('/var/ipfire/red/iface') // 'red0';
    $iface =~ /^[A-Za-z0-9_.:-]+$/ or $iface = 'red0';

    # Helper to read a counter safely
    my $read_counter = sub {
        my ($type) = @_;
        my $path = "/sys/class/net/$iface/statistics/${type}_bytes";
        my $val  = read_file($path);
        return (defined $val && $val =~ /^\d+$/) ? int($val) : 0;
    };

    # First snapshot
    my $rx1 = $read_counter->('rx');
    my $tx1 = $read_counter->('tx');

    # Short pause – 1 second
    sleep 1;

    # Second snapshot
    my $rx2 = $read_counter->('rx');
    my $tx2 = $read_counter->('tx');

    # Convert delta (bytes/s) → Mbit/s
    my $rx_mbps = sprintf("%.2f", (($rx2 - $rx1) * 8) / 1_000_000);
    my $tx_mbps = sprintf("%.2f", (($tx2 - $tx1) * 8) / 1_000_000);

    return ($rx_mbps, $tx_mbps);
}

# Obtain the current speed
my ($rx_mbps, $tx_mbps) = get_red_speed();

# --- CARD 6: Connection Status ---
# ---- Connection Status card (inside the <section class='ha-card'> block) ----
print "<section class='ha-card'><h3>" . esc(('Connection Status')) . "</h3>\n";
print "<dl class='ha-table'>\n";

# State badge
my $state = lc($conn->{state} // 'unknown');
print "<dt>" . esc(('State')) . "</dt><dd>" . status_badge($state) . "</dd>\n";

if ( $state eq 'connected' ) {
    my $since_ts  = $conn->{connected_since} // 0;
    my $since_txt = ($since_ts =~ /^\d+$/) ? fmt_since($since_ts) : esc($since_ts);
    my $dur_txt   = $conn->{duration_text} // '';
    $dur_txt = fmt_time($conn->{duration} // 0) if !defined $dur_txt || $dur_txt eq '';
    print "<dt>" . esc(('Connected For')) . "</dt><dd>" . esc($since_txt) . "</dd>\n";
}
else {
    print "<dt>" . esc(('Connected For')) . "</dt><dd>N/A</dd>\n";
}

# -----------------------------------------------------------------
#  Profile – show a clickable link to fireinfo.ipfire.org
# -----------------------------------------------------------------
my $pub_id = read_file("${General::swroot}/fireinfo/public_id") // 'N/A';
my $esc_id = esc($pub_id);                     # HTML-escape the id

print "<dt>" . esc('Profile') . "</dt>";
print "<dd>\n<a href=\"https://fireinfo.ipfire.org/profile/$esc_id\" target=\"_blank\">" 
    . $esc_id 
    . "</a></dd>\n";
print "<dt>External IP</dt><dd>", esc(read_file("${General::swroot}/red/local-ipaddress") // 'N/A'), "</dd>\n";
print "<dt>External hostname</dt><dd>",  $settings{'HOSTNAME'}.$settings{'DOMAINNAME'}, "</dd>\n";

# ---- RED traffic (two separate rows) ----
# --- Replace your current RED traffic block with this: ---
print "<dt>", esc(('RED Traffic')), "</dt><dd></dd>\n";
print "<dt>&nbsp;In</dt><dd><span id=\"red-rx-rate\">--</span> Mbit/s</dd>\n";
print "<dt>&nbsp;Out</dt><dd><span id=\"red-tx-rate\">--</span> Mbit/s</dd>\n";


print "</dl>\n";   # end of <dl class='ha-table'>
print "</section>\n";   # end of the Connection‑status card

print "</div>\n"; # ha-grid
print "</div>\n"; # ha-page
# -----------------------------------------------------------------
# Real-time traffic polling script (Updates every 2 seconds)
# -----------------------------------------------------------------
print <<'END_SCRIPT';
<script>
(function() {
    let lastRx = null;
    let lastTx = null;
    let lastTime = null;

    async function pollTraffic() {
        try {
            const res = await fetch('/cgi-bin/api.cgi', { cache: 'no-store' });
            if (!res.ok) return;

            const json = await res.json();
            if (!json.traffic) return;

            const now = Date.now();
            const curRx = json.traffic.rx_bytes;
            const curTx = json.traffic.tx_bytes;

            if (lastTime !== null && lastRx !== null && lastTx !== null) {
                const elapsedSec = (now - lastTime) / 1000;

                if (elapsedSec > 0) {
                    const deltaRx = Math.max(0, curRx - lastRx);
                    const deltaTx = Math.max(0, curTx - lastTx);

                    // Convert (Bytes/sec * 8) to Mbit/s
                    const rxMbps = ((deltaRx * 8) / (elapsedSec * 1_000_000)).toFixed(2);
                    const txMbps = ((deltaTx * 8) / (elapsedSec * 1_000_000)).toFixed(2);

                    const elRx = document.getElementById('red-rx-rate');
                    const elTx = document.getElementById('red-tx-rate');

                    if (elRx) elRx.textContent = rxMbps;
                    if (elTx) elTx.textContent = txMbps;
                }
            }

            lastRx = curRx;
            lastTx = curTx;
            lastTime = now;
        } catch (err) {
            console.warn('Live speed update failed:', err);
        }
    }

    // Run immediately to establish baseline, then every 2 seconds
    pollTraffic();
    setInterval(pollTraffic, 2000);
})();
</script>
END_SCRIPT

&Header::closebox();
&Header::closebigbox();
&Header::closepage();

exit 0;
