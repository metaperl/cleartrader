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
use lib join '/', File::Spec->splitdir( dirname(__FILE__) ), 'lib';
use Local::DB;

# config/setup
my $wallet = 'sSzgkxNoWFq9bMMF7F6zUeCFe36yomhoRd';

my $mode = hostname =~ /linode/ ? 'production' : 'dev';
my $sandbox = $mode eq 'dev';

warn "mode:$mode:sandbox:$sandbox";

my $errors_occurred;
my $debug = 4;

my $q_width   = 2;
my $admin_fee = 1.00;

helper pay_amount => sub {
    my ( $self, $amount ) = @_;

    my $percentage_gain = 0.8 * $amount;
    $amount + $percentage_gain;
};

my %base_url = (
    dev        => "http://localhost:3000",
    production => "http://www.elcaminoclaro.com"
);

my $base_url = $base_url{$mode};

my %solid = ( host => 'localhost', port => 8555, auth => 'user:pass' );

my $json = {
    jsonrpc => '1.0',
    id      => 'curltest',
    method  => 'getnewaddress'
};

# BEGIN mojolicious

helper da => sub {

    my $da = Local::DB->new->da;
};

helper auto_inviter => sub {
    my ($self) = @_;

    $self->da->sqlrowhash(
        'SELECT 
   u1.id,u1.username, COUNT(u2.sponsor_id) AS refcount FROM users u1 LEFT JOIN users u2 ON (u1.id=u2.sponsor_id)
WHERE u1.id >= 4
GROUP BY u1.id,u1.username
ORDER BY refcount ASC, u1.id ASC
LIMIT 1'
    );
};

helper customer => sub {
    my ( $self, $email ) = @_;

    warn "E:$email:";

    $self->da->sqlrowhash(
        sql_interp
"SELECT * FROM users u INNER JOIN user_statuses us ON (u.status_id=us.id) WHERE email = ",
        \$email
    );
};

helper customer_via_username => sub {
    my ( $self, $username ) = @_;

    $self->da->sqlrowhash(
        sql_interp
"SELECT * FROM users u INNER JOIN user_statuses us ON (u.status_id=us.id) WHERE username = ",
        \$username
    );
};

helper 'queues' => sub {

    my ($self) = @_;

    my $viewed = $self->da->sqlarrayhash( "
    SELECT
      *
    FROM
      payment_queues
    ORDER BY
      id ASC
    "
    );

    # returns an arrayref of hashrefs
    #warn Data::Dumper::Dumper( 'paymentqs', $viewed );

    $viewed;

};

helper 'recent_transactions' => sub {

    my ($self) = @_;

    my $viewed = $self->da->sqlarrayhash( "
    SELECT
      action, value, username, t.ts
    FROM
      transactions t INNER JOIN users u ON (id=user_id)
    ORDER BY
      t.ts DESC
    LIMIT 10
    "
    );

    # returns an arrayref of hashrefs
    #    warn Data::Dumper::Dumper( 'viewed', $viewed );

    $viewed;

};

helper 'active_in_queue' => sub {

    my ( $self, $amount ) = @_;

    my $viewed = $self->da->sqlarrayhash( "
    SELECT
      *
    FROM
      slot_purchases sp INNER JOIN users ON (id=user_id)
    WHERE 
      position_price = $amount 
      AND status IS NULL
    ORDER BY
      sp.ts ASC
    "
    );

    $viewed;

};

helper 'get_user_by_id' => sub {
    my ( $self, $id ) = @_;

    my $viewed = $self->da->sqlrowhash( "
    SELECT
      *
    FROM
      users
    WHERE
      id=$id
    "
    );

};

helper dumper => sub {
    my ( $self, @struct ) = @_;
    warn Dumper(@struct);
};

plugin 'Bcrypt';

plugin 'Authentication' => {
    'session_key' => 'wickedapp',
    'load_user'   => sub {
        my ( $self, $email ) = @_;
        $self->customer($email);
    },
    'validate_user' => sub {
        my ( $self, $email, $entered_pass, $extradata ) = @_;
        my $C = $self->customer($email);

        $self->dumper( C => $C );

        return undef unless scalar keys %$C;

        my $crypted_pass = $C->{password};

        warn "if ( $self->bcrypt_validate( $entered_pass, $crypted_pass ) ) {";

        if ( $self->bcrypt_validate( $entered_pass, $crypted_pass ) ) {
            $self->session->{user} = $C;
            $self->dumper( userdata => $self->session->{user} );
            $email;
        }
        else {
            undef;
        }
    },
};

get '/' => sub {
    my $self = shift;

    my $msg;

    use Cwd;
    my $c = getcwd;

    $self->render( template => 'index' );

};

get '/dela/:inviter' => sub {
    my ( $self, $inviter ) = @_;
    my $I = $self->customer_via_username($inviter);

    $self->redirect_to("/register?inviter=$I->{id}");

};

get '/faq' => sub {
    my $self = shift;

    $self->render( template => 'faq' );

};

get '/starting' => sub {

};

get '/questions' => sub {
    my $self = shift;

    $self->render( template => 'questions' );

};

get '/chat' => sub {
    my $self = shift;

    $self->render( template => 'chat' );

};

get '/terms' => sub {
    my $self = shift;

    $self->render( template => 'terms' );

};

get '/register' => sub {
    my $self = shift;

    my ( $type, $inviter, $inviter_id ) = do {
        if ( $self->param('inviter') ) {
            my $username = $self->param('inviter');
            my $id       = $self->customer_via_username($username)->{id};
            ( direct => $username, $id );
        }
        else {
	  my $i = $self->auto_inviter;
            ( automatic => $i->{username}, $i->{id} );
        }
    };

    $self->render(
        template    => 'register',
        inviter     => $inviter,
        invite_type => $type,
        sponsor_id  => $inviter_id
    );
};

sub address_to_site {
    use Mojo::JSON;
    my $J = Mojo::JSON->new;

    use Mojo::UserAgent;
    my $ua = Mojo::UserAgent->new;

    $json->{method} = 'getnewaddress';

    $json = $J->encode($json);

    my $tx =
      $ua->post( "http://$solid{auth}" . '@'
          . "$solid{host}:$solid{port}" => { Connection => 'close' } => $json );

    my $hash = $J->decode( $tx->res->body );

    die Dumper($hash) if $hash->{error};

    $hash->{result};
}

post '/register_eval' => sub {
    my $self = shift;

    my @param = $self->param;
    my %param = map { $_ => $self->param($_) } @param;

    #delete $param{password_again};
    $param{password} = $self->bcrypt( delete $param{password_again} );

    $param{address_to_site} = address_to_site();

    # my $c = $self->customer_via_username( delete $param{invited_by} );
    # $param{sponsor_id} = $c->{id};

    delete $param{$_} for qw(invite_type inviter);

    $self->dumper( 'register_eval_param' => \%param );

    my $rows = $self->da->do( sql_interp( "INSERT INTO users", \%param ) );

    $self->render( template => 'thankyou' );

};

any '/cancel' => sub {
    my ($self) = @_;
    $self->redirect_to('/root');
};

get '/logout' => sub {
    my ($self) = @_;
    $self->logout;
    $self->redirect_to('/');
};

under sub {
    my ($self) = @_;

    warn 'authing user';

    return 1
      if (
        $self->authenticate( $self->param('email'), $self->param('password') )
        or $self->session->{user} );
    app->log->debug('Authentication FAILED');
    $self->redirect_to('/');
};

any '/root' => sub {
    my $self = shift;

    $self->dumper( justbeforerender => $self->session->{user} );
    $self->render(
        template => 'root',
        msg      => '',
        user     => $self->session->{user}
    );

};

get '/settings' => sub {
    my ($self) = @_;

    #  my $url = $self->tx->req->url

    $self->render(
        template => 'settings',
        user     => $self->session->{user}
    );

};

get '/give' => sub {
    my ($self) = @_;

    #  my $url = $self->tx->req->url

    $self->render(
        template => 'give',
        user     => $self->session->{user},
        address  => $wallet,
        payqs    => $self->queues
    );

};

=for pod

getinfo

sc_getmining
sc_setmining
sc_getmining

listaccounts - list accounts
getaddressesbyaccount <account> - list addresses in an account

getreceivedbyaddress

getnewaddress

listreceivedbyaddress




=cut

post '/give_eval' => sub {
    my ($self) = @_;

    #  my $url = $self->tx->req->url
    my $donation_id = $self->param('donation');
    my @q           = @{ $self->queues };
    $self->dumper( Q => \@q );
    my ($href) = grep { $_->{id} == $donation_id } @q;
    $self->dumper( DONATION_ID => $donation_id, HREF => $href );
    my $payment = $href->{amount};

    $self->render(
        template => 'give_eval',
        user     => $self->session->{user},
        payment  => $payment,
        address  => $wallet,

    );

};

get '/invite' => sub {
    my ($self) = @_;

    #  my $url = $self->tx->req->url

    $self->render(
        template => 'invite',
        user     => $self->session->{user}
    );

};

helper pay => sub {
    my ( $self, $amount ) = @_;

    warn 1;

    my $rows = $self->da->sqlarrayhash(
        sql_interp(
            "SELECT position_price, transaction_id, email, username, u.id
FROM slot_purchases sp INNER JOIN users u ON (user_id=id)
WHERE STATUS IS NULL AND position_price =", \$amount, "ORDER BY sp.ts ASC"
        )
    );

    warn Dumper( 'rows', $rows );

    return unless @$rows > $q_width;

    warn 1;

    my $pay_amount = $self->pay_amount($amount);

    my $payee = $rows->[0];

    warn Dumper( 'payee', $payee );

    my $status;
    unless ($status) {

        warn 'payout into transactions';

        my %xact = (
            user_id => $payee->{id},
            action  => 'payout',
            amount  => sprintf '$%.2f slot',
            $amount
        );

        $rows =
          $self->da->do( sql_interp( "INSERT into transactions", \%xact ) );

    }

    $self->render(
        template => 'root',

    );

};

get '/order' => sub {
    my ($self) = @_;

};

any '/buy' => sub {
    my $self = shift;

    my $ordered = $self->param('positionprice');

    $self->session->{positionprice} = $ordered;

    my $OrderTotal = sprintf '%.2f', $ordered + $admin_fee;

    #warn Dumper( 'PYPALDS', $P, 'TOTOL', $OrderTotal );

};

# Start the Mojolicious command system
app->defaults( layout => 'cam' );
app->secret('laverne&sherley')->start;

