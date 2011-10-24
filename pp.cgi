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

use Business::PayPal::API::ExpressCheckout;
use Sys::Hostname;

use Local::DB;
use Local::PayPal::Config;


my $mode = hostname =~ /linode/ ? 'production' : 'dev';
my $sandbox = $mode eq 'dev';

warn "mode:$mode:sandbox:$sandbox";

my $errors_occurred;
my $debug = 4;

my $paypal_config = Local::PayPal::Config->new($mode);

# --- edit these

my $q_width = 2;
my $admin_fee = 1.00;
helper pay_amount => sub {
  my($self, $amount)=@_;
  
  my $percentage_gain = 0.8 * $amount;
  $amount + $percentage_gain;
};

# --- end edit

#die Dumper($paypal_config);

my $pp_email     = $paypal_config->{email};
my $pp_username  = $paypal_config->{username};
my $pp_password  = $paypal_config->{password};
my $pp_signature = $paypal_config->{signature};

my %pp_args = (
    Username  => $pp_username,
    Password  => $pp_password,
    Signature => $pp_signature,
    sandbox   => $sandbox
);

my %pay_url = (
    dev        => 'https://svcs.sandbox.paypal.com/AdaptivePayments/Pay',
    production => 'https://svcs.paypal.com/AdaptivePayments/Pay',
);

my %checkout = (
    dev        => "https://www.sandbox.paypal.com",
    production => "https://www.paypal.com"
);

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

    my %xact = (
        user_id => $self->session->{user}->{id},
        action  => 'buy',
        amount  => sprintf '%d dollar slot',
        $self->session->{positionprice}
    );

    $rows = $self->da->do( sql_interp( "INSERT into transactions", \%xact ) );

    $self->pay( $self->session->{positionprice} );

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

    use Business::PayPal::API::MassPay;
    my $pp = Business::PayPal::API::MassPay->new(%pp_args);

    warn 1;
    my $url = $pay_url{$mode};
    my $tx  = $self->ua->post_form(
        $url, 'UTF-8',
        {
            'requestEnvelope.errorLanguage'   => 'en_US',
            actionType                        => 'PAY',
            senderEmail                       => $pp_email,
            'receiverList.receiver(0).email'  => $payee->{email},
            'receiverList.receiver(0).amount' => $pay_amount,
            currencyCode                      => 'USD',
            feesPayer                         => 'EACHRECEIVER',
            memo                              => 'slot payout',
            cancelUrl                         => "$base_url/cancel",
            returnUrl                         => "$base_url/return",
            ipnNotificationUrl                => "$base_url/ipn"
        },
        {
            "X-PAYPAL-SECURITY-USERID"      => $pp_username,
            "X-PAYPAL-SECURITY-PASSWORD"    => $pp_password,
            "X-PAYPAL-SECURITY-SIGNATURE"   => $pp_signature,
            "X-PAYPAL-REQUEST-DATA-FORMAT"  => 'NV',
            "X-PAYPAL-RESPONSE-DATA-FORMAT" => "NV",
            "X-PAYPAL-APPLICATION-ID"       => 'APP-80W284485P519543T'
        }
    );

    #    warn Dumper( 'resp',

    my $params = Mojo::Parameters->new( $tx->res->body );

    my $ack = $params->param('responseEnvelope.ack');
    warn "ack:$ack";

    my $status = $ack =~ /success/i ? 0 : $tx->res->body;

    $rows = $self->da->do(
        sql_interp(
            "UPDATE slot_purchases SET status = ", \$status,
            "WHERE transaction_id=",               \$payee->{transaction_id}
        )
    );

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
        msg      => Dumper( $tx->res->body ),
        user     => $self->session->{user}
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

    use Business::PayPal::API::ExpressCheckout;

    use Data::Dumper;

    my $pp = new Business::PayPal::API::ExpressCheckout(
        Username  => $pp_username,
        Password  => $pp_password,
        Signature => $pp_signature,
        sandbox   => $sandbox
    );

    warn "
    my $pp = Business::PayPal::API::ExpressCheckout->new(
        Username  => $pp_username,
        Password  => $pp_password,
        Signature => $pp_signature,
        sandbox   => $sandbox
    )";

    $Business::PayPal::API::Debug = 1;

    my $url = $base_url{$mode};

    warn "URL:$url";

    my $ReturnURL        = "$url/return";
    my $CancelURL        = "$url/cancel";
    my $InvoiceID        = int rand 5000;
    my $OrderDescription = sprintf
      '$%.2f total: a %d dollar slot + $%.2f admin fee ',
      $OrderTotal, $ordered, $admin_fee;

    warn Dumper( 'PP', $pp );
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
    $url = $checkout{$mode};
    $url = "$url/cgi-bin/webscr?cmd=_express-checkout&token=$token";
    warn "url:$url";
    $self->redirect_to($url);

};

# Start the Mojolicious command system
app->defaults( layout => 'cam' );
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

