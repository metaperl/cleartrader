use strict;
use warnings;

use Mojo::Util;

my $host = 'li2-168.members.linode.com';
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

=pod

This is an example of how to write a client to 
send a command to an rpc server

That server needs to have an rpcallowip in its solidcoin.conf that allows
this code to make a json-rpc connection to it.

This example makes use of the excellent L<Mojolicious|http://mojolicio.us> 
Web in a Box for perl - clients, servers, everything you need for cutting edge
HTML5 development in Perl.

=cut
