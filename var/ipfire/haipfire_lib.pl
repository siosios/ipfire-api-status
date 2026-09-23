#!/usr/bin/perl
###############################################################################
# HA-IPFire Shared Library (Fixed load order & lazy JSON)
# Place at: /var/ipfire/haipfire_lib.pl
###############################################################################

package Haipfire::Lib;

use strict;
use warnings;
use Exporter qw(import);

# 1. Load IPFire core first – this makes the General:: helpers available.
require '/var/ipfire/general-functions.pl';
require '/opt/pakfire/lib/functions.pl';

our @EXPORT_OK = qw(
    read_file
    json_bool
    traffic_data
    system_data
    fireinfo_data
    services_data
    addons_data
);

# -----------------------------------------------------------------------------
# Simple helpers
# -----------------------------------------------------------------------------
sub read_file {
    my ($path) = @_;
    open my $fh, '<', $path or return undef;
    local $/;
    my $data = <$fh>;
    close $fh;
    return undef unless defined $data;
    chomp $data;
    return $data;
}

# Lazy loader – JSON::PP is imported only when we really need it.
sub _json_pp {
    return JSON::PP->new->utf8->canonical;
}

sub json_bool {
    my ($v) = @_;
    return $_[0] ? _json_pp()->true : _json_pp()->false;
}

# -----------------------------------------------------------------------------
# Traffic – read directly from sysfs (no external modules)
# -----------------------------------------------------------------------------
sub traffic_data {
    my $iface = read_file('/var/ipfire/red/iface');
    return (0, 0) unless defined $iface && $iface =~ /^[A-Za-z0-9_.:-]+$/;

    my $rx = read_file("/sys/class/net/$iface/statistics/rx_bytes");
    my $tx = read_file("/sys/class/net/$iface/statistics/tx_bytes");

    return (0, 0) unless defined $rx && defined $tx && $rx =~ /^\d+$/ && $tx =~ /^\d+$/;
    return (int($rx), int($tx));
}

# -----------------------------------------------------------------------------
# System information
# -----------------------------------------------------------------------------
sub system_data {
    my $ver   = read_file('/etc/system-release') // '';
    my $pfs   = &Pakfire::status();
    my %pfs   = ref($pfs) eq 'HASH' ? %$pfs : ();
    my $core  = (($pfs{'CoreUpdateAvailable'} // '') eq 'yes');
    my $pkg   = $pfs{'PakUpdatesAvailable'} // 0;
    $pkg = 0 unless $pkg =~ /^\d+$/;
    return ($ver, $core, $pkg);
}

# -----------------------------------------------------------------------------
# Fireinfo – reads the JSON profile file and extracts a few fields
# -----------------------------------------------------------------------------
sub fireinfo_data {
    my $profile_file = '/var/ipfire/fireinfo/profile';
    open my $fh, '<', $profile_file
      or return ( ('') x 12 );
    local $/;
    my $json = <$fh>;
    close $fh;

    my $jp = eval { _json_pp() } or return ( ('') x 12 );
    my $data = eval { $jp->decode($json) };
    return ( ('') x 12 ) if $@ || ref($data) ne 'HASH';

    my $p = $data->{'profile'} // {};
    my $c = $p->{'cpu'} // {};
    my $n = $p->{'network'} // {};
    my $s = $p->{'system'} // {};

    return (
        $c->{'arch'}          // '',
        $c->{'model_string'}  // '',
        int($c->{'count'} // 0),
        $s->{'model'} // '',
        $s->{'vendor'} // '',
        int($s->{'memory'} // 0),
        int($s->{'root_size'} // 0),
        $s->{'virtual'} ? 1 : 0,
        $n->{'blue'}   ? 1 : 0,
        $n->{'green'}  ? 1 : 0,
        $n->{'orange'} ? 1 : 0,
        $n->{'red'}    ? 1 : 0,
    );
}

# -----------------------------------------------------------------------------
# Services – simply check whether a PID/pidfile exists
# -----------------------------------------------------------------------------
sub services_data {
    my %svcs = (
        'dhcp'              => { process => 'dhcpd' },
        'web_server'        => { process => 'httpd' },
        'cron'              => { process => 'fcron' },
        'dns_resolver'      => { process => 'kresd' },
        'logging'           => { process => 'syslogd' },
        'ntp'               => { process => 'ntpd' },
        'ssh'               => { process => 'sshd' },
        'vpn'               => { process => 'charon' },
        'web_proxy'         => { process => 'squid' },
        'ips'               => { pidfile => '/var/run/suricata.pid' },
        'ovpn_roadwarrior'  => { process => 'openvpn', pidfile => '/var/run/openvpn-rw.pid' },
        'lldp'              => { process => 'lldpd' },
        'dbus'              => { process => 'dbus-daemon', pidfile => '/var/run/dbus/pid' },
    );
    my %st;
    for my $k (keys %svcs) {
        my $cfg = $svcs{$k};
        my @pids = defined $cfg->{pidfile}
          ? &General::read_pids( $cfg->{pidfile} )
          : &General::find_pids( $cfg->{process} );
        $st{$k} = @pids ? 1 : 0;
    }
    return %st;
}

# -----------------------------------------------------------------------------
# Add‑on information
# -----------------------------------------------------------------------------
sub addons_data {
    my %addons;

    my %paklist = &Pakfire::dblist("installed");

    foreach my $pak (sort keys %paklist) {
        my %metadata = &Pakfire::getmetadata($pak, "installed");

        next unless "$metadata{'Services'}";

        foreach my $service (split(/ /, "$metadata{'Services'}")) {
            next unless $service;

            my @status = &General::system_output(
                "/usr/local/bin/addonctrl",
                "$pak",
                "status",
                "$service"
            );

            my $output = join('', @status);

            my $running =
                ($output =~ /is\ running/ && $output !~ /is\ not\ running/);

            $addons{$pak} = {
                'running' => $running ? 1 : 0,
            };
        }
    }

    return %addons;
}

1;    # <-- must return true for a Perl module
