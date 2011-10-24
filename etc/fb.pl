use Finance::Bitcoin::API;
 
my $uri     = 'http://user:password@127.0.0.1:8332/';
my $api     = Finance::Bitcoin::API->new( endpoint => $uri );
my $balance = $api->call('getbalance');
print $balance;
