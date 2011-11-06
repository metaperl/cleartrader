use strict;
use warnings;

use Mojo::Util;

my $host = 'localhost';
my $port = 8555;
my $auth = "user:pass";

my $json = {
	    jsonrpc => '1.0',
	    id => 'curltest',
	    method => 'getinfo'
	   };
use Mojo::JSON;
$json = Mojo::JSON->new->encode($json);
	    
use Mojo::UserAgent;
my $ua = Mojo::UserAgent->new;

my $tx  = $ua->post(
    "http://$auth" . '@' . "$host:$port" => {Connection => 'close'} => $json
);

warn $tx->res->body;
