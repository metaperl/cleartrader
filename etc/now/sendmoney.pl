use strict;
use warnings;

use Mojo::Util;

my $host = 'li2-168.members.linode.com';
my $port = 8555;
my $auth = "user:pass";
my $to   = 'sRpk3Qv6s5G4UQPVDucPrhHc5ZVFdYMhLJ';
my $amount = 0.567;

my $json = {
    jsonrpc => '1.0',
    id      => 'curltest',
    method  => 'sendtoaddress',
    params  => [ $to, $amount, "Payout to bob", "Payout to john" ]
};
use Mojo::JSON;
my $J = Mojo::JSON->new;
$json = $J->encode($json);

use Mojo::UserAgent;
my $ua = Mojo::UserAgent->new;

my $tx =
  $ua->post( "http://$auth" . '@'
      . "$host:$port" => { Connection => 'close' } => $json );

my $body = $tx->res->body;
warn $body;

my $hash = $J->decode($body);
warn $hash->{result};

# http://blockexplorer.ahimoth.com/Home/TransactionDetails?transactionHash=8f7638456ac3895696489ee287d08ddd6def18551faca9a9e5b08679d5d52487
