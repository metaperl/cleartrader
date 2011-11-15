#!/usr/bin/env perl

use strict;
use warnings;

# core modules
use Data::Dumper;
use File::Basename 'dirname';
use File::Spec;
use List::Util qw(sum);

# cpan modules
use Mojolicious::Lite;
use autodie qw/:all/;
use DBI;    #DBI->trace(1);
use SQL::Interp qw/:all/;
use Sys::Hostname;

# local modules
use lib join '/', File::Spec->splitdir( dirname(__FILE__) ), '..', 'lib';
use Local::DB;
use Local::Bitcoin;

my $bitcoin = Local::Bitcoin->new;

my $da = Local::DB->new->da;

DBI->trace(1);

my @m = $da->sqlrowhash('SELECT * FROM v_missing_pledges');
for my $m (@m) {

    my $amount = $bitcoin->json_query(getreceivedbyaddress => [$m->{address}]);
    warn Dumper($m, $amount);

    process_received_pledge($m,$amount) if ($amount > 0);
}

sub process_received_pledge {
    my($m,$amount)=@_;

    update_user_pledges($m);
    record_transaction($m,$amount);
    upgrade_user($m);
    distribute_pledge($m, $amount);

}

sub update_user_pledges {
    my($m)=@_;

    $da->do(sql_interp(
		"UPDATE user_pledges SET ts_received = NOW() WHERE",
		$m));
}

sub record_transaction {
    my($m,$amount)=@_;

    my %T = (
	user_id => $m->{pledger_id},
	action => 'sent_pledge',
	value => $amount);
    

    $da->do(sql_interp(
		"INSERT INTO transactions", \%T));
}

sub upgrade_user {
    my($m,$amount)=@_;

    my %T = (
	id => $m->{pledger_id},
	receiving_level => $amount,
	status_id => 2
	);

    $da->do(sql_interp(
		"UPDATE user SET", \%T));

}

