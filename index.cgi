#!/usr/bin/env perl

use strict;
use warnings;

use autodie qw/:all/;

use Data::Dumper;
use File::Basename 'dirname';
use File::Spec;

use lib join '/', File::Spec->splitdir( dirname(__FILE__) ), 'lib';

use Mojolicious::Lite;

use List::Util qw(sum);

use DBI;
#DBI->trace(1);
use SQL::Interp qw/:all/;

use Sys::Hostname;

use Local::DB;



my $mode = hostname =~ /linode/ ? 'production' : 'dev';
my $sandbox = $mode eq 'dev';

warn "mode:$mode:sandbox:$sandbox";

my $errors_occurred;
my $debug = 4;


# --- edit these

my $q_width = 2;
my $admin_fee = 1.00;
helper pay_amount => sub {
  my($self, $amount)=@_;
  
  my $percentage_gain = 0.8 * $amount;
  $amount + $percentage_gain;
};

# --- end edit


my %base_url = (
    dev        => "http://localhost:3000",
    production => "http://www.elcaminoclaro.com"
);

my $base_url = $base_url{$mode};




helper paypal_fees => sub {
    my ( $self, $amount ) = @_;

    my $percent      = $amount * .029;
    my $thirty_cents = 0.30;
    {
        percent_amount => $percent,
        thirty_cents   => $thirty_cents
    };
};

helper da => sub {


    my $da = Local::DB->new->da;
};

helper customer => sub {
    my ( $self, $email ) = @_;

    #die "E:$email:";

    $self->da->sqlrowhash( sql_interp "SELECT * FROM users WHERE email = ",
        \$email );
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
    #warn Data::Dumper::Dumper( 'viewed', $viewed );

    $viewed;

};

helper 'recent_transactions' => sub {

    my ($self) = @_;

    my $viewed = $self->da->sqlarrayhash( "
    SELECT
      action, amount, username, t.ts
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

# helper dumper => sub {
#     my ( $self, @struct ) = @_;
#     Dumper( \@struct );
# };

plugin 'Authentication' => {
    'session_key' => 'wickedapp',
    'load_user'   => sub {
        my ( $self, $email ) = @_;
        $self->customer($email);
    },
    'validate_user' => sub {
        my ( $self, $email, $password, $extradata ) = @_;
        my $C = $self->customer($email);
        return undef unless scalar keys %$C;

        if ( $password eq $C->{password} ) {
            $self->session->{user} = $C;
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

get '/register' => sub {
    my $self = shift;

    $self->render( template => 'register' );

};

get '/faq' => sub {
    my $self = shift;

    $self->render( template => 'faq' );

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

post '/register_eval' => sub {
    my $self = shift;

    my @param = $self->param;
    my %param = map { $_ => $self->param($_) } @param;

    delete $param{password_again};

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
    return 1
      if (
        $self->authenticate( $self->param('email'), $self->param('password') )
        or $self->session->{user} );
    app->log->debug('Authentication FAILED');
    $self->redirect_to('/');
};

any '/root' => sub {
    my $self = shift;

    $self->render(
        template => 'root',
        msg      => '',
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
app->secret('clear')->start;


