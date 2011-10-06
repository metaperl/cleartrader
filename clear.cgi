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
DBI->trace(1);
use SQL::Interp qw/:all/;

app->defaults( layout => 'cam' );

use Business::PayPal::API::ExpressCheckout;
use Local::PayPal::Config;

my $errors_occurred;
my $debug = 4;

my $paypal_config = Local::PayPal::Config->new;

my $pp_username = $paypal_config->username;
$pp_username = 'cleart_1317787692_biz_api1.gmail.com';

my $pp_password = $paypal_config->password;
$pp_password = '1317787729';

my $pp_signature = $paypal_config->signature;
$pp_signature = 'ACUJJ0QSXgMyI2hh-LYPGuJxVGFBAbFNgamI72WhQVK5grpnVaShah5x';

my $sandbox = 1;

my $admin_fee = 1.00;

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
    use Local::DB;

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
    warn Data::Dumper::Dumper( 'viewed', $viewed );

    $viewed;

};

helper 'recent_transactions' => sub {

    my ($self) = @_;

    my $viewed = $self->da->sqlarrayhash( "
    SELECT
      *
    FROM
      transactions
    ORDER BY
      ts DESC
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

any '/return' => sub {
    my ($self)  = @_;
    my $token   = $self->param('token');
    my $PayerID = $self->param('PayerID');

    my $pp = Business::PayPal::API::ExpressCheckout->new(
        Username  => $pp_username,
        Password  => $pp_password,
        Signature => $pp_signature,
        sandbox   => $sandbox
    );

    my %details = $pp->GetExpressCheckoutDetails($token);

    warn "------GetExpressCheckoutDetails---------\n";
    warn Data::Dumper->Dump( [ \%details ], [qw(details)] );
    warn "----------------------------------------\n";

    # hat's geklappt?
    if ( $details{Ack} ne "Success" ) {
        &error_exit(
            "PayPal hat \""
              . $details{'Ack'}
              . "\" gemeldet: ("
              . $details{'Errors'}[0]->{'ErrorCode'} . ") "
              . $details{'Errors'}[0]->{'LongMessage'}
              . " (CorrelationID: "
              . $details{'CorrelationID'} . ")",
            28
        );
    }

    #my $PayerID = $details{PayerID};
    print "PayerID: $PayerID\n";

    foreach my $field ( keys %details ) {
        next if $field =~ /^PayerID|Token|Version|Build|Ack$/;

        print $field, ": ", $details{$field}, "\n";
    }

    my $OrderTotal = $self->session->{ $details{Token} };

    my %payinfo = $pp->DoExpressCheckoutPayment(
        Token         => $token,
        PaymentAction => 'Sale',
        PayerID       => $PayerID,
        OrderTotal    => $OrderTotal,
    );

    warn "----DoExpressCheckoutPayment---------------\n";
    my $dump = Data::Dumper->Dump( [ \%payinfo ], [qw(payinfo)] );
    warn $dump;
    warn "-------------------------------------------\n";

    # hat's geklappt?
    if ( $payinfo{'Ack'} ne "Success" ) {
        &error_exit(
                "PayPal hat \""
              . $payinfo{'Ack'}
              . "\" gemeldet: ("
              . $payinfo{'Errors'}[0]->{'ErrorCode'} . ") "
              . $payinfo{'Errors'}[0]->{'LongMessage'}
              . " (CorrelationID: "
              . $payinfo{'CorrelationID'} . ")",
        );
    }

    foreach my $field ( keys %payinfo ) {
        next if $field =~ /^PayerID|Token|Version|Build|Ack$/;

        print $field, ": ", $payinfo{$field}, "\n";
    }

    use YAML::XS;

    my %slot_purchase = (
        user_id             => $self->session->{user}->{id},
        position_price      => $self->session->{positionprice},
        transaction_id      => $payinfo{TransactionID},
        transaction_details => $dump
    );

    my $rows = $self->da->do(
        sql_interp( "INSERT INTO slot_purchases", \%slot_purchase ) );

    my $xaction = sprintf '%d dollar slot purchase by %s',
      $self->session->{positionprice},
      $self->session->{user}->{username};

    warn "XACTION:$xaction:";

    $rows = $self->da->do(
        sql_interp( "INSERT into transactions", { text => $xaction } ) );

    $self->render( text => 'Payment is complete' );

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

    my $msg;

    use Cwd;
    my $c = getcwd;

    $self->render( template => 'root', user => $self->session->{user} );

};

get '/order' => sub {
    my ($self) = @_;

};

any '/buy' => sub {
    my $self = shift;

    my $ordered = $self->param('positionprice');

    $self->session->{positionprice} = $ordered;

    my $P = $self->paypal_fees($ordered);
    $P->{ordered}   = $ordered;
    $P->{admin_fee} = $admin_fee;

    my $OrderTotal = sprintf '%.2f', sum( values %$P );

    warn Dumper( 'PYPALDS', $P, 'TOTOL', $OrderTotal );

    use Business::PayPal::API::ExpressCheckout;

    use Data::Dumper;

    my $pp = new Business::PayPal::API::ExpressCheckout(
        Username  => $pp_username,
        Password  => $pp_password,
        Signature => $pp_signature,
        sandbox   => $sandbox
    );

    $Business::PayPal::API::Debug = 1;

    my $ReturnURL        = 'http://localhost:3000/return';
    my $CancelURL        = 'http://localhost:3000/cancel';
    my $InvoiceID        = int rand 5000;
    my $OrderDescription = sprintf
'$%.2f total for a %d dollar slot, $%.2f admin fee, and $%.2f in paypal fees',
      $OrderTotal, $P->{ordered}, $P->{admin_fee},
      $P->{percent_amount} + $P->{thirty_cents};

    my %response = $pp->SetExpressCheckout(
        OrderTotal => $OrderTotal,
        MaxAmount  => $OrderTotal,  # es fällt keine Steuer und kein Shipping an
        currencyID => 'USD',
        InvoiceID  => $InvoiceID,
        NoShipping => 1,

        OrderDescription => $OrderDescription,
        ReturnURL        => $ReturnURL,
        CancelURL        => $CancelURL,
    );

    warn "----SetExpressCheckout---------------\n";
    warn Data::Dumper->Dump( [ \%response ], [qw(response)] );
    warn "-------------------------------------\n";

    $self->session->{ $response{Token} } = $OrderTotal;

    # hat's geklappt?
    if ( $response{'Ack'} ne "Success" ) {
        &error_exit(
            "PayPal hat \""
              . $response{'Ack'}
              . "\" gemeldet: ("
              . $response{'Errors'}[0]->{'ErrorCode'} . ") "
              . $response{'Errors'}[0]->{'LongMessage'}
              . " (CorrelationID: "
              . $response{'CorrelationID'} . ")",
            18
        );
    }

    my $token = $response{'Token'};

    print "Token: $token\n";

#    $self->redirect_to("https://www.paypal.com/cgi-bin/webscr?cmd=_express-checkout&token=$token");
    $self->redirect_to(
"https://www.sandbox.paypal.com/cgi-bin/webscr?cmd=_express-checkout&token=$token"
    );

};

# Start the Mojolicious command system
app->secret('clear')->start;

############################################
# Hilfsroutinen
############################################
sub print_error {
    my ($text) = @_;

    print STDERR "ERROR: " . $text . "\n";

    $errors_occurred++;

    if ( $errors_occurred > 10 ) {
        print STDERR
          "ERROR: Zu viele Fehler ($errors_occurred) aufgetreten -> Abbruch\n";
        &cleanup_and_exit();
    }
}

sub print_debug {
    my ( $text, $debug_level ) = @_;

    $debug_level = 0 unless $debug_level;

    if ( $debug >= $debug_level ) {
        print "DEBUG($debug_level): " . $text . "\n";
    }
}

sub error_exit {
    my ( $text, $exitcode ) = @_;

    &print_error($text);
    &cleanup_and_exit($exitcode);
}

# nötige Aufräumarbeiten am Ende
sub cleanup {
    &print_debug( "cleanup done.", 1 );
}

# Exitcode als optionaler Parameter
sub cleanup_and_exit {
    my ($exitcode) = @_;
    $exitcode = 0 unless $exitcode;

    &cleanup();

    if ($errors_occurred) {
        &print_debug(
            "Fertig, aber es sind $errors_occurred Fehler aufgetreten.\n", 1 );
        exit 100 + $errors_occurred unless $exitcode;
    }

    &print_debug( "self (vERSION) beendet.\n", 1 );
    exit $exitcode;
}

