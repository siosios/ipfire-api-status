#!/usr/bin/perl
###############################################################################
# HA-IPFire API Endpoint (JSON Only)
# Place at: /srv/web/ipfire/cgi-bin/api.cgi
###############################################################################

use strict;
use warnings;

# ---------------------------------------------------------
# Load IPFire core libraries first
# ---------------------------------------------------------
require '/var/ipfire/general-functions.pl';
require '/opt/pakfire/lib/functions.pl';
require '/var/ipfire/haipfire_lib.pl';

Haipfire::Lib->import(
    qw( read_file traffic_data system_data fireinfo_data services_data addons_data )
);

use JSON::PP ();

my $jp = JSON::PP->new->utf8->canonical;

# ---------------------------------------------------------
# Helper to send JSON with proper HTTP headers
# ---------------------------------------------------------
sub send_json {
    my ($payload) = @_;

    print "Content-Type: application/json; charset=utf-8\r\n";
    print "Cache-Control: no-store, no-cache, must-revalidate\r\n";
    print "Pragma: no-cache\r\n";
    print "X-Content-Type-Options: nosniff\r\n";
    print "\r\n";

    print $jp->encode($payload);
    exit 0;
}

# ---------------------------------------------------------
# Reject non‑GET requests early
# ---------------------------------------------------------
my $method = uc ( $ENV{REQUEST_METHOD} // 'GET' );
if ( $method ne 'GET' ) {
    send_json(
        {
            api_version => 1,
            error       => 'method_not_allowed',
        }
    );
}

# ---------------------------------------------------------
# Gather data
# ---------------------------------------------------------
my $final;

eval {
    # System / kernel / etc.
    my ( $version, $core_update, $package_updates ) = system_data();

    my $pakfire_version = Pakfire::make_version() // '';

    my @kv = General::system_output( "uname", "-r" );
    my $kernel_release = $kv[0] // '';
    chomp $kernel_release;

    my (
        $arch,
        $cpu_model,
        $cpu_cnt,
        $model,
        $vendor,
        $mem,
        $root_sz,
        $virt,
        $blue,
        $green,
        $orange,
        $red
    ) = fireinfo_data();

    # Services
    my %svc = services_data();

    # Add‑ons
    my %addons = addons_data();

    # Traffic
    my ( $rx_bytes, $tx_bytes ) = traffic_data();

    # Connection status (identical to original script)
    my $state   = 'disconnected';
    my $duration        = 0;
    my $connected_since = undef;

    my %ppps = ();
    &General::readhash( "${General::swroot}/ppp/settings", \%ppps );

    my $active = "${General::swroot}/red/active";

    if ( -e $active ) {
        my @st = stat($active);
        if ( @st && $st[9] ) {
            $connected_since = int( $st[9] );
            $duration        = time() - $connected_since;
            $duration        = 0 if $duration < 0;
            $state           = 'connected';
        }
    }
    else {
        my $keep = "${General::swroot}/red/keepconnected";
        if ( -e $keep ) {
            my $pppd_up = system( "ps -ef | grep -q '[p]ppd'" ) == 0;
            $state = 'connecting' if $pppd_up;
        }
    }

    my $profile = $ppps{'PROFILENAME'} // '';

    my $conn = {
        state          => $state,
        profile        => $profile,
    };
    if ( $state eq 'connected' ) {
        $conn->{connected_since} = $connected_since // 0;
        $conn->{duration}        = int($duration);
        my $dur_text = General::format_time( int($duration) );
        $conn->{duration_text}   = $dur_text if defined $dur_text;
    }
    else {
        $conn->{connected_since} = undef;
        $conn->{duration}        = 0;
        $conn->{duration_text}   = '';
    }

    # Build final Perl structure
    my $sys = {
        version            => $version,
        pakfire_version    => $pakfire_version,
        kernel_version     => $kernel_release,
        architecture       => $arch,
        cpu_model          => $cpu_model,
        cpu_count          => $cpu_cnt,
        model              => $model,
        vendor             => $vendor,
        memory             => $mem,
        root_size          => $root_sz,
        virtual            => $virt ? $jp->true : $jp->false,
        core_update        => $core_update ? $jp->true : $jp->false,
        package_updates    => $package_updates + 0,
    };

    my $net = {
        blue   => $blue   ? $jp->true : $jp->false,
        green  => $green  ? $jp->true : $jp->false,
        orange => $orange ? $jp->true : $jp->false,
        red    => $red    ? $jp->true : $jp->false,
    };

    my $srv = {};
    for my $k (qw(
        dhcp web_server cron dns_resolver logging ntp ssh vpn web_proxy ips ovpn_roadwarrior lldp dbus
      )) {
        $srv->{$k} = $svc{$k} ? $jp->true : $jp->false;
    }

    my $addon_arr = [];
    for my $name ( sort keys %addons ) {
        push @$addon_arr, {
            name    => $name,
            running => $addons{$name}{running} ? $jp->true : $jp->false,
        };
    }

    my $traffic = {
        rx_bytes => $rx_bytes + 0,
        tx_bytes => $tx_bytes + 0,
    };

    $final = {
        api_version => 1,
        system      => $sys,
        network     => $net,
        services    => $srv,
        addons      => $addon_arr,
        traffic     => $traffic,
        connection  => $conn,
    };
};

if ($@) {
    send_json(
        {
            api_version => 1,
            error       => 'collection_failed',
            message     => $@,
        }
    );
}

send_json($final);
