use strict;
use warnings;

use Mojo::Util;

my $host = 'localhost';
my $port = 8666;
my $auth = "user:pass";

my $json = {
    jsonrpc => '1.0',
    id      => 'curltest',
    method  => 'getnewaddress'
};
use Mojo::JSON;
my $J = Mojo::JSON->new;
$json = $J->encode($json);

use Mojo::UserAgent;
my $ua = Mojo::UserAgent->new;

my $tx =
  $ua->post( "http://$auth" . '@'
      . "$host:$port" => { Connection => 'close' } => $json );

my $hash = $J->decode( $tx->res->body );

use Data::Dumper;
warn Dumper($hash);

