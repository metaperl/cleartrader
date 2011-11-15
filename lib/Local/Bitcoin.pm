package Local::Bitcoin;



use Moose;


has 'json' => ( is => 'rw', default => sub {
    return { jsonrpc => '1.0',
	     json_id => 'local-bitcoin'
    };

		});
# has 'json_jsonrpc' => ( is => 'rw', default => '1.0' );
# has 'json_id' => ( is => 'rw', default => 'curltest' );
# has 'json_method' => ( is => 'rw', default => 'getnewaddress' );

has 'username' => ( is => 'ro', default => 'metaperl' );
has 'password' => ( is => 'ro', default => 'metapass' );
has 'host' => ( is => 'ro', default => 'localhost' );
has 'port' => (
    is      => 'ro',
    default => '8332'
    );
has 'minconf' => (is => 'rw', default => 6);

use Data::Dumper;

sub auth {
    my($self)=@_;
    sprintf '%s:%s', $self->username, $self->password;
}

sub json_query {
    my($self, $method, $params)=@_;
    
    my $json = $self->json;

    use Mojo::JSON;
    my $J = Mojo::JSON->new;

    use Mojo::UserAgent;
    my $ua = Mojo::UserAgent->new;

    $json->{method} = $method;
    $json->{params} = $params;

    warn Dumper( JSON => $json );

    $json = $J->encode($json);
    
    my $url = sprintf 'http://%s@%s:%d',
    $self->auth, $self->host, $self->port;


    my $tx =
	$ua->post( $url => { Connection => 'close' } => $json );

    my $hash = $J->decode( $tx->res->body );

    die Dumper($hash) if $hash->{error};

    $hash->{result};
};


1;
